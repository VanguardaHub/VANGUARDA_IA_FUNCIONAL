from dotenv import load_dotenv
load_dotenv()

import os
import json
import uuid
import asyncio
import base64
import random
import secrets
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import bcrypt
import jwt
import httpx
from html import escape
from urllib.parse import urlparse
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, BackgroundTasks, Depends, UploadFile, File, Form, Header
import hmac
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone, ImageContent
from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration

from io import BytesIO
import pypdf
import docx as docx_lib
import openpyxl

from payments import payments_router
import re
import ipaddress
from html.parser import HTMLParser
import nekt

ROOT_DIR = Path(__file__).parent
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Vanguarda.IA")
api_router = APIRouter(prefix="/api")

JWT_ALGORITHM = "HS256"
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")

AI_MODELS = {
    "gpt-5.4-mini": {"provider": "openai", "model": "gpt-5.4-mini", "label": "GPT-5.4 Mini"},
    "claude-sonnet-4-6": {"provider": "anthropic", "model": "claude-sonnet-4-6", "label": "Claude Sonnet 4.6"},
}

PIECE_TYPES = {
    "post_instagram": "Post de Instagram (feed)",
    "stories": "Stories (Instagram/Facebook)",
    "anuncio_meta": "Anúncio Meta Ads (Facebook/Instagram)",
    "anuncio_linkedin": "Anúncio LinkedIn",
    "email_marketing": "E-mail marketing",
    "blog": "Artigo de blog / SEO",
}

# ---------------- Cost tracking (custo de IA por etapa) ----------------
DEFAULT_PRICING = {
    "usd_to_brl": 5.40,
    "markup_pct": 100.0,
    "models": {
        "gpt-5.4-mini": {"input_per_m": 0.15, "output_per_m": 0.60},
        "claude-sonnet-4-6": {"input_per_m": 3.00, "output_per_m": 15.00},
    },
    "image_high_per_unit": 0.19,
}

STAGE_LABELS = {
    "copy": "Copy (texto)",
    "refacao_texto": "Refação de texto",
    "imagem": "Imagem",
    "refacao_imagem": "Refação de imagem",
    "agente": "Agente operacional",
}

def _merge_pricing(user_pricing):
    import copy as _copy
    p = _copy.deepcopy(DEFAULT_PRICING)
    if isinstance(user_pricing, dict):
        for k in ("usd_to_brl", "markup_pct", "image_high_per_unit"):
            if user_pricing.get(k) is not None:
                try:
                    p[k] = float(user_pricing[k])
                except (TypeError, ValueError):
                    pass
        for mid, mp in (user_pricing.get("models") or {}).items():
            if mid in p["models"] and isinstance(mp, dict):
                for kk in ("input_per_m", "output_per_m"):
                    if mp.get(kk) is not None:
                        try:
                            p["models"][mid][kk] = float(mp[kk])
                        except (TypeError, ValueError):
                            pass
    return p

async def get_pricing(user_id: str) -> dict:
    s = await db.app_settings.find_one({"user_id": user_id}, {"_id": 0, "pricing": 1})
    return _merge_pricing((s or {}).get("pricing"))

def _text_cost_usd(model: str, input_tokens: int, output_tokens: int, pricing: dict) -> float:
    mp = pricing["models"].get(model, DEFAULT_PRICING["models"]["gpt-5.4-mini"])
    return (input_tokens / 1_000_000) * mp["input_per_m"] + (output_tokens / 1_000_000) * mp["output_per_m"]

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0

async def record_cost(user_id, gen_group_id, stage, model, input_tokens=0, output_tokens=0, images=0, client_id=None, extra_usd=0.0):
    pricing = await get_pricing(user_id)
    usd = float(extra_usd)
    if input_tokens or output_tokens:
        usd += _text_cost_usd(model, input_tokens, output_tokens, pricing)
    if images:
        usd += images * pricing["image_high_per_unit"]
    brl = round(usd * pricing["usd_to_brl"], 4)
    doc = {
        "id": f"cost_{uuid.uuid4().hex[:12]}", "user_id": user_id,
        "gen_group_id": gen_group_id, "piece_id": None, "client_id": client_id,
        "stage": stage, "model": model,
        "input_tokens": int(input_tokens), "output_tokens": int(output_tokens),
        "images": int(images), "cost_usd": round(usd, 6), "cost_brl": brl,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.ai_costs.insert_one(doc)
    doc.pop("_id", None)
    return doc

async def stage_for(user_id, gen_group_id, kind: str) -> str:
    base = ["copy", "refacao_texto"] if kind == "texto" else ["imagem", "refacao_imagem"]
    if not gen_group_id:
        return base[0]
    existing = await db.ai_costs.count_documents({"user_id": user_id, "gen_group_id": gen_group_id, "stage": {"$in": base}})
    return base[0] if existing == 0 else base[1]


# ---------------- Auth helpers ----------------

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def get_jwt_secret() -> str:
    return os.environ["JWT_SECRET"]

def create_access_token(user_id: str, email: str, token_version: int = 0) -> str:
    payload = {"sub": user_id, "email": email, "ver": token_version,
               "exp": datetime.now(timezone.utc) + timedelta(minutes=15), "type": "access"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str, token_version: int = 0) -> str:
    payload = {"sub": user_id, "ver": token_version,
               "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "refresh"}
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def set_jwt_cookies(response: Response, user: dict):
    ver = user.get("token_version", 0)
    response.set_cookie("access_token", create_access_token(user["user_id"], user["email"], ver),
                        httponly=True, secure=True, samesite="none", max_age=900, path="/")
    response.set_cookie("refresh_token", create_refresh_token(user["user_id"], ver),
                        httponly=True, secure=True, samesite="none", max_age=604800, path="/")

def public_user(user: dict) -> dict:
    user = dict(user)
    user.pop("_id", None)
    user.pop("password_hash", None)
    return user

async def get_user_by_session_token(token: str) -> Optional[dict]:
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        return None
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("session_token")
    if token:
        user = await get_user_by_session_token(token)
        if user:
            return user
    token = request.cookies.get("access_token")
    auth_header = request.headers.get("Authorization", "")
    if not token and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if token:
        user = await get_user_by_session_token(token)
        if user:
            return user
        try:
            payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
            if payload.get("type") != "access":
                raise HTTPException(status_code=401, detail="Token inválido")
            user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
            if not user:
                raise HTTPException(status_code=401, detail="Usuário não encontrado")
            if payload.get("ver", 0) != user.get("token_version", 0):
                raise HTTPException(status_code=401, detail="Sessão expirada")
            return user
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expirado")
        except jwt.InvalidTokenError:
            pass
    raise HTTPException(status_code=401, detail="Não autenticado")

async def get_admin_user(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return user

# ---------------- Activity / event logs ----------------

async def log_activity(user_id: str, kind: str, message: str, meta: dict = None):
    await db.activity_logs.insert_one({
        "id": f"log_{uuid.uuid4().hex[:12]}", "user_id": user_id, "kind": kind,
        "message": message, "meta": meta or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

# ---------------- Password reset email ----------------

EMAIL_BASE_URL = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip().rstrip("/") or "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY", "")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME") or "Vanguarda.IA"

async def send_password_reset_email(to_email: str, token: str) -> bool:
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    link = f"{base}/reset-password?token={token}"
    if not EMAIL_KEY or EMAIL_KEY.startswith("{") or not base.startswith("https://"):
        if urlparse(base).hostname in ("localhost", "127.0.0.1", "::1"):
            logger.warning("Email não configurado; link de reset: %s", link)
        else:
            logger.error("E-mail de reset não configurado (EMERGENT_EMAIL_KEY / FRONTEND_URL)")
        return False
    brand = escape(EMAIL_FROM_NAME)
    html = (
        f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif">'
        f'<p>Recebemos uma solicitação para redefinir sua senha do {brand}.</p>'
        f'<p><a href="{escape(link)}">Redefinir minha senha</a></p>'
        f'<p>Este link expira em 1 hora e só pode ser usado uma vez. Se você não solicitou, ignore este e-mail.</p>'
        f'<p style="font-size:12px;color:#888">Enviado por {brand}. Nunca pedimos sua senha por e-mail.</p>'
        f'</td></tr></table>'
    )
    try:
        async with httpx.AsyncClient(timeout=30) as http_client:
            resp = await http_client.post(
                f"{EMAIL_BASE_URL}/api/v1/email/send",
                headers={"X-Email-Key": EMAIL_KEY},
                json={"to": [to_email], "subject": f"Redefina sua senha do {EMAIL_FROM_NAME}",
                      "html": html, "from_name": EMAIL_FROM_NAME},
            )
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Falha ao enviar e-mail de reset: {e}")
        return False

# ---------------- Pydantic schemas ----------------

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ClientCreate(BaseModel):
    name: str
    segment: str = ""
    contact_name: str = ""
    contact_email: str = ""
    brand_color: str = "#6366F1"
    notes: str = ""

class ClientUpdate(BaseModel):
    name: Optional[str] = None
    segment: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    brand_color: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

class GeneratePieceRequest(BaseModel):
    client_id: Optional[str] = None
    piece_type: str
    model: str = "gpt-5.4-mini"
    tone: str = "profissional"
    prompt: str
    gen_group_id: Optional[str] = None

class PieceSaveRequest(BaseModel):
    client_id: Optional[str] = None
    title: str
    piece_type: str
    model: str
    prompt: str = ""
    content: str
    image: Optional[str] = None
    status: str = "rascunho"
    gen_group_id: Optional[str] = None

class PieceUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None

class PublishRequest(BaseModel):
    scheduled_at: Optional[str] = None

class ImageGenRequest(BaseModel):
    prompt: str
    client_id: Optional[str] = None
    gen_group_id: Optional[str] = None

class BibleDocCreate(BaseModel):
    title: str
    category: str = "Geral"
    content: str

class BibleAskRequest(BaseModel):
    question: str
    model: str = "gpt-5.4-mini"

class CampaignCreate(BaseModel):
    client_id: str
    name: str
    objective: str = "Conversões"
    budget_daily: float = 100.0
    status: str = "ativa"

class CampaignStatusUpdate(BaseModel):
    status: str

class AlertRuleCreate(BaseModel):
    name: str
    metric: str
    operator: str
    threshold: float

class SettingsUpdate(BaseModel):
    default_model: Optional[str] = None
    default_tone: Optional[str] = None
    agency_name: Optional[str] = None
    meta_connected: Optional[bool] = None
    pricing: Optional[dict] = None

class AdminUserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)
    role: str = "member"
    plan: str = "trial"

class AdminUserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    plan: Optional[str] = None
    password: Optional[str] = None

# ---------------- Auth endpoints ----------------

def _is_owner_email(email: str) -> bool:
    owner = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    return bool(owner) and email.lower() == owner

async def ensure_owner_admin(user: dict) -> dict:
    """Garante que o e-mail do dono (ADMIN_EMAIL) sempre tenha papel de admin,
    mesmo que a conta tenha sido criada via Google antes do seed rodar."""
    if _is_owner_email(user["email"]) and user.get("role") != "admin":
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"role": "admin", "plan": "agency"}})
        user["role"] = "admin"
        user["plan"] = "agency"
    return user


@api_router.post("/auth/register")
async def register(req: RegisterRequest, response: Response):
    email = req.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    user = {
        "user_id": user_id, "email": email, "name": req.name,
        "password_hash": hash_password(req.password), "role": "member",
        "picture": None, "plan": "trial", "token_version": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(user)
    await db.app_settings.insert_one({
        "user_id": user_id, "default_model": "gpt-5.4-mini",
        "default_tone": "profissional", "agency_name": "", "meta_connected": False,
    })
    set_jwt_cookies(response, user)
    await log_activity(user_id, "auth", f"Nova conta criada: {email}")
    return public_user(user)

@api_router.post("/auth/login")
async def login(req: LoginRequest, request: Request, response: Response):
    email = req.email.lower()
    identifier = f"{request.client.host if request.client else 'unknown'}:{email}"
    attempts = await db.login_attempts.count_documents({
        "identifier": identifier,
        "created_at": {"$gt": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()},
    })
    if attempts >= 5:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde 15 minutos.")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user or not user.get("password_hash") or not verify_password(req.password, user["password_hash"]):
        await db.login_attempts.insert_one({
            "identifier": identifier, "email": email,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos")
    await db.login_attempts.delete_many({"identifier": identifier})
    user = await ensure_owner_admin(user)
    set_jwt_cookies(response, user)
    return public_user(user)

@api_router.post("/auth/google/session")
async def google_session(request: Request, response: Response):
    body = await request.json()
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    credential = body.get("credential")

    # --- Fluxo OAuth próprio (hospedagem externa): verifica o id_token do Google ---
    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    if google_client_id and credential:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        try:
            gdata = google_id_token.verify_oauth2_token(
                credential, google_requests.Request(), google_client_id
            )
        except ValueError:
            raise HTTPException(status_code=401, detail="Token Google inválido")
        if not gdata.get("email_verified", False):
            raise HTTPException(status_code=401, detail="E-mail Google não verificado")
        email = gdata["email"].lower()
        user = await db.users.find_one({"email": email}, {"_id": 0})
        if not user:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            user = {
                "user_id": user_id, "email": email, "name": gdata.get("name", email.split("@")[0]),
                "picture": gdata.get("picture"),
                "role": "admin" if _is_owner_email(email) else "member",
                "plan": "agency" if _is_owner_email(email) else "trial",
                "token_version": 0, "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.users.insert_one(user)
            await db.app_settings.insert_one({
                "user_id": user_id, "default_model": "gpt-5.4-mini",
                "default_tone": "profissional", "agency_name": "", "meta_connected": False,
            })
            await log_activity(user_id, "auth", f"Nova conta via Google: {email}")
        else:
            await db.users.update_one({"email": email}, {"$set": {"name": gdata.get("name", user["name"]), "picture": gdata.get("picture")}})
            user["name"] = gdata.get("name", user["name"])
            user["picture"] = gdata.get("picture")
        user = await ensure_owner_admin(user)
        set_jwt_cookies(response, user)
        return public_user(user)

    # --- Fluxo gerenciado pelo Emergent (preview): usa session_id ---
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id ausente")
    async with httpx.AsyncClient(timeout=30) as http_client:
        resp = await http_client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Sessão Google inválida")
    data = resp.json()
    email = data["email"].lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id, "email": email, "name": data.get("name", email.split("@")[0]),
            "picture": data.get("picture"),
            "role": "admin" if _is_owner_email(email) else "member",
            "plan": "agency" if _is_owner_email(email) else "trial",
            "token_version": 0, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user)
        await db.app_settings.insert_one({
            "user_id": user_id, "default_model": "gpt-5.4-mini",
            "default_tone": "profissional", "agency_name": "", "meta_connected": False,
        })
        await log_activity(user_id, "auth", f"Nova conta via Google: {email}")
    else:
        await db.users.update_one({"email": email}, {"$set": {"name": data.get("name", user["name"]), "picture": data.get("picture")}})
        user["name"] = data.get("name", user["name"])
        user["picture"] = data.get("picture")
    user = await ensure_owner_admin(user)
    session_token = data["session_token"]
    await db.user_sessions.insert_one({
        "user_id": user["user_id"], "session_token": session_token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc),
    })
    response.set_cookie("session_token", session_token, httponly=True, secure=True,
                        samesite="none", max_age=604800, path="/")
    return public_user(user)

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_many({"session_token": token})
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    response.delete_cookie("session_token", path="/")
    return {"message": "Sessão encerrada"}

@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return public_user(user)

@api_router.post("/auth/refresh")
async def refresh(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Sem refresh token")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token inválido")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
    user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
    if not user or payload.get("ver", 0) != user.get("token_version", 0):
        raise HTTPException(status_code=401, detail="Sessão expirada")
    response.set_cookie("access_token", create_access_token(user["user_id"], user["email"], user.get("token_version", 0)),
                        httponly=True, secure=True, samesite="none", max_age=900, path="/")
    return {"message": "ok"}

@api_router.post("/auth/forgot-password")
async def forgot_password(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    email = (body.get("email") or "").lower().strip()
    generic = {"message": "Se o e-mail estiver cadastrado, enviamos um link de redefinição."}
    since = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    await db.password_reset_requests.insert_one({"email": email, "created_at": datetime.now(timezone.utc).isoformat()})
    recent = await db.password_reset_requests.count_documents({"email": email, "created_at": {"$gt": since}})
    total_recent = await db.password_reset_requests.count_documents({"created_at": {"$gt": since}})
    if recent > 5 or total_recent > 8:
        return generic
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        return generic
    token = secrets.token_urlsafe(32)
    await db.password_reset_tokens.insert_one({
        "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        "user_id": user["user_id"], "email": email,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        "used": False,
    })
    background_tasks.add_task(send_password_reset_email, user["email"], token)
    return generic

@api_router.post("/auth/reset-password")
async def reset_password(request: Request):
    body = await request.json()
    token = body.get("token") or ""
    new_password = body.get("password") or ""
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="A senha deve ter ao menos 6 caracteres")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    doc = await db.password_reset_tokens.find_one_and_update(
        {"token_hash": token_hash, "used": False, "expires_at": {"$gt": datetime.now(timezone.utc)}},
        {"$set": {"used": True}},
    )
    if not doc:
        raise HTTPException(status_code=400, detail="Link inválido ou expirado")
    email = doc["email"]
    await db.users.update_one({"email": email}, {
        "$set": {"password_hash": hash_password(new_password)},
        "$inc": {"token_version": 1},
    })
    await db.password_reset_tokens.delete_many({"email": email, "used": False})
    await db.login_attempts.delete_many({"email": email})
    return {"message": "Senha redefinida com sucesso"}

# ---------------- Dashboard ----------------

def campaign_metrics_series(campaign_id: str, days: int = 30) -> List[dict]:
    series = []
    today = datetime.now(timezone.utc).date()
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        rng = random.Random(f"{campaign_id}-{day.isoformat()}")
        impressions = rng.randint(3000, 18000)
        clicks = int(impressions * rng.uniform(0.008, 0.035))
        spend = round(rng.uniform(40, 220), 2)
        conversions = int(clicks * rng.uniform(0.02, 0.12))
        series.append({
            "date": day.isoformat(), "impressions": impressions, "clicks": clicks,
            "spend": spend, "conversions": conversions,
        })
    return series

@api_router.get("/dashboard")
async def dashboard(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    clients_count = await db.clients.count_documents({"user_id": uid})
    pieces_count = await db.pieces.count_documents({"user_id": uid})
    campaigns = await db.campaigns.find({"user_id": uid}, {"_id": 0}).to_list(100)
    active_campaigns = [c for c in campaigns if c.get("status") == "ativa"]
    total_spend = total_impressions = total_clicks = total_conversions = 0
    for c in campaigns:
        for m in c.get("metrics", []):
            total_spend += m["spend"]
            total_impressions += m["impressions"]
            total_clicks += m["clicks"]
            total_conversions += m["conversions"]
    revenue = total_conversions * 87.5
    roas = round(revenue / total_spend, 2) if total_spend else 0
    ctr = round((total_clicks / total_impressions) * 100, 2) if total_impressions else 0
    daily = {}
    for c in campaigns:
        for m in c.get("metrics", [])[-30:]:
            d = daily.setdefault(m["date"], {"date": m["date"], "spend": 0, "clicks": 0, "impressions": 0, "conversions": 0})
            d["spend"] += m["spend"]
            d["clicks"] += m["clicks"]
            d["impressions"] += m["impressions"]
            d["conversions"] += m["conversions"]
    series = sorted(daily.values(), key=lambda x: x["date"])
    recent_activity = await db.activity_logs.find({"user_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(8)
    recent_pieces = await db.pieces.find({"user_id": uid}, {"_id": 0, "image": 0}).sort("created_at", -1).to_list(5)
    since_30d = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    ai_cost_docs = await db.ai_costs.find({"user_id": uid, "created_at": {"$gte": since_30d}}, {"_id": 0, "cost_brl": 1}).to_list(20000)
    ai_cost_brl = round(sum(c["cost_brl"] for c in ai_cost_docs), 4)
    pricing = await get_pricing(uid)
    mk = 1 + pricing["markup_pct"] / 100
    return {
        "kpis": {
            "clients": clients_count, "pieces": pieces_count,
            "active_campaigns": len(active_campaigns), "total_campaigns": len(campaigns),
            "spend": round(total_spend, 2), "impressions": total_impressions,
            "clicks": total_clicks, "conversions": total_conversions,
            "ctr": ctr, "roas": roas, "revenue": round(revenue, 2),
            "ai_cost_brl": ai_cost_brl, "ai_billable_brl": round(ai_cost_brl * mk, 4),
        },
        "series": series,
        "recent_activity": recent_activity,
        "recent_pieces": recent_pieces,
    }

# ---------------- Clients ----------------

@api_router.get("/clients")
async def list_clients(user: dict = Depends(get_current_user)):
    clients = await db.clients.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    for c in clients:
        c["campaigns_count"] = await db.campaigns.count_documents({"client_id": c["id"]})
        c["pieces_count"] = await db.pieces.count_documents({"client_id": c["id"]})
    return clients

@api_router.post("/clients")
async def create_client(req: ClientCreate, user: dict = Depends(get_current_user)):
    doc = req.model_dump()
    doc.update({
        "id": f"cli_{uuid.uuid4().hex[:12]}", "user_id": user["user_id"],
        "status": "ativo", "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.clients.insert_one(doc)
    await log_activity(user["user_id"], "cliente", f"Novo cliente cadastrado: {req.name}")
    doc.pop("_id", None)
    return doc

@api_router.get("/clients/{client_id}")
async def get_client(client_id: str, user: dict = Depends(get_current_user)):
    c = await db.clients.find_one({"id": client_id, "user_id": user["user_id"]}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    c["campaigns"] = await db.campaigns.find({"client_id": client_id}, {"_id": 0}).to_list(50)
    c["pieces"] = await db.pieces.find({"client_id": client_id}, {"_id": 0, "image": 0}).sort("created_at", -1).to_list(50)
    return c

@api_router.put("/clients/{client_id}")
async def update_client(client_id: str, req: ClientUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    result = await db.clients.update_one({"id": client_id, "user_id": user["user_id"]}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return await db.clients.find_one({"id": client_id}, {"_id": 0})

@api_router.delete("/clients/{client_id}")
async def delete_client(client_id: str, user: dict = Depends(get_current_user)):
    result = await db.clients.delete_one({"id": client_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    await db.campaigns.delete_many({"client_id": client_id})
    await log_activity(user["user_id"], "cliente", f"Cliente removido: {client_id}")
    return {"message": "Cliente removido"}

# ---------------- AI piece generation ----------------

async def build_brand_context(user_id: str, client_id: Optional[str]) -> str:
    parts = []
    if client_id:
        c = await db.clients.find_one({"id": client_id, "user_id": user_id}, {"_id": 0})
        if c:
            parts.append(f"Cliente: {c['name']} | Segmento: {c.get('segment', 'não informado')} | Observações da marca: {c.get('notes', 'nenhuma')}")
    docs = await db.bible_documents.find({"user_id": user_id}, {"_id": 0}).to_list(20)
    if docs:
        snippets = "\n".join(f"- {d['title']}: {d['content'][:400]}" for d in docs[:5])
        parts.append(f"Base de conhecimento da agência (Bíblia):\n{snippets}")
    return "\n\n".join(parts)

@api_router.post("/pieces/generate")
async def generate_piece(req: GeneratePieceRequest, user: dict = Depends(get_current_user)):
    if req.model not in AI_MODELS:
        raise HTTPException(status_code=400, detail="Modelo de IA inválido")
    if req.piece_type not in PIECE_TYPES:
        raise HTTPException(status_code=400, detail="Tipo de peça inválido")
    model_cfg = AI_MODELS[req.model]
    context = await build_brand_context(user["user_id"], req.client_id)
    system = (
        "Você é diretor(a) de criação sênior da Vanguarda.IA, especialista em copywriting de marketing para agências brasileiras. "
        "Escreva sempre em português do Brasil (pt-BR), com qualidade de nível profissional e PRONTA para publicar: gancho forte, storytelling, clareza, ritmo e foco em conversão. "
        "Entregue a peça no formato nativo do canal, com quebras de linha bem pensadas e emojis usados com bom gosto quando fizer sentido. "
        "NUNCA use rótulos como 'TÍTULO:', 'LEGENDA:', 'CORPO:', 'CTA:' nem qualquer metacomentário, aspas envolvendo o texto ou explicação. Responda apenas com a peça final."
    )
    context_block = f"Contexto da marca:\n{context}\n\n" if context else ""
    prompt = (
        f"Formato da peça: {PIECE_TYPES[req.piece_type]}.\n"
        f"Tom de voz: {req.tone}.\n"
        f"Briefing: {req.prompt}\n\n"
        f"{context_block}"
        "Regras de saída:\n"
        "1) Primeira linha: um título/gancho curto e magnético (sem prefixo, sem aspas).\n"
        "2) Deixe uma linha em branco e escreva o corpo completo da peça no formato ideal para o canal, com parágrafos curtos e escaneáveis.\n"
        "3) Finalize com uma chamada para ação (CTA) clara e específica.\n"
        "4) Se o canal for social (Instagram, Stories, Meta Ads, LinkedIn), acrescente ao final uma única linha com 6 a 12 hashtags relevantes.\n"
        "5) Se for e-mail marketing, a primeira linha deve ser um assunto irresistível, seguido do corpo do e-mail.\n"
        "Capriche: entregue no nível de um profissional sênior, sem clichês vazios."
    )

    async def event_stream():
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"piece-{uuid.uuid4().hex[:8]}",
                system_message=system,
            ).with_model(model_cfg["provider"], model_cfg["model"])
            in_tok = out_tok = 0
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    yield f"data: {json.dumps({'delta': ev.content})}\n\n"
                elif isinstance(ev, StreamDone):
                    if ev.usage:
                        in_tok = ev.usage.input_tokens or 0
                        out_tok = ev.usage.output_tokens or 0
                    break
            stage = await stage_for(user["user_id"], req.gen_group_id, "texto")
            cost = await record_cost(user["user_id"], req.gen_group_id, stage, req.model, in_tok, out_tok, client_id=req.client_id)
            await log_activity(user["user_id"], "geracao", f"Peça gerada com {model_cfg['label']} ({PIECE_TYPES[req.piece_type]})")
            yield f"data: {json.dumps({'done': True, 'stage': stage, 'cost_brl': cost['cost_brl'], 'tokens': in_tok + out_tok})}\n\n"
        except Exception as e:
            logger.error(f"Erro na geração: {e}")
            yield f"data: {json.dumps({'error': 'Falha na geração com IA. Tente novamente.'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

async def expand_image_prompt(brief: str, context: str) -> str:
    """Expande um briefing curto em um prompt de direção de arte rico e detalhado,
    imitando o rewriting automático do ChatGPT. Usa LLM de texto (barato em créditos)."""
    brand_block = f"\n\nBRAND GUIDELINES (must obey strictly — colors, tone, audience, restrictions):\n{context}" if context else ""
    system = (
        "You are a world-class advertising art director and prompt engineer for text-to-image models (gpt-image-1). "
        "Turn a short brief into ONE single, richly detailed, production-ready image prompt in ENGLISH, the way ChatGPT auto-expands prompts. "
        "Describe explicitly: main subject(s) and their exact appearance/wardrobe/expression, the scene and props, camera framing and composition, "
        "lighting, a concrete cohesive color palette, mood, and rendering style (choose photographic, 3D, or illustration based on the brief). "
        "If the brief implies a marketing poster, specify the EXACT on-image text (headline, subheadline, CTA) with clean, well-kerned typography and where it sits, "
        "leaving balanced negative space for it. Add professional quality descriptors (ultra-detailed, sharp focus, high resolution, agency-grade finish, no watermark, no distorted text). "
        "Obey the brand guidelines when provided. Output ONLY the final image prompt, no preamble, no quotes, no explanations."
    )
    user_msg = f"Brief (may be in Portuguese): {brief}{brand_block}"
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"imgprompt-{uuid.uuid4().hex[:8]}",
            system_message=system,
        ).with_model("openai", "gpt-5.4-mini")
        parts = []
        in_tok = out_tok = 0
        async for ev in chat.stream_message(UserMessage(text=user_msg)):
            if isinstance(ev, TextDelta):
                parts.append(ev.content)
            elif isinstance(ev, StreamDone):
                if ev.usage:
                    in_tok = ev.usage.input_tokens or 0
                    out_tok = ev.usage.output_tokens or 0
                break
        expanded = "".join(parts).strip()
        return (expanded or brief, in_tok, out_tok)
    except Exception as e:
        logger.error(f"Falha ao expandir prompt de imagem: {e}")
        return (brief, 0, 0)

async def _run_image_job(job_id: str, user_id: str, prompt: str, client_id: Optional[str], gen_group_id: Optional[str] = None):
    try:
        pricing = await get_pricing(user_id)
        context = await build_brand_context(user_id, client_id)
        detailed, ein, eout = await expand_image_prompt(prompt, context)
        exp_usd = _text_cost_usd("gpt-5.4-mini", ein, eout, pricing)
        gen = OpenAIImageGeneration(api_key=EMERGENT_LLM_KEY)
        images = await gen.generate_images(
            prompt=detailed, model="gpt-image-1", number_of_images=1, quality="high",
        )
        b64 = base64.b64encode(images[0]).decode()
        stage = await stage_for(user_id, gen_group_id, "imagem")
        cost = await record_cost(user_id, gen_group_id, stage, "gpt-image-1", images=1, client_id=client_id, extra_usd=exp_usd)
        await db.image_jobs.update_one({"id": job_id}, {"$set": {
            "status": "done", "image": f"data:image/png;base64,{b64}",
            "cost_brl": cost["cost_brl"], "stage": stage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})
        await log_activity(user_id, "geracao", "Imagem gerada com IA (GPT Image 1)")
    except Exception as e:
        logger.error(f"Erro ao gerar imagem (job {job_id}): {e}")
        await db.image_jobs.update_one({"id": job_id}, {"$set": {
            "status": "error", "error": "Falha ao gerar imagem com IA",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }})

@api_router.post("/pieces/generate-image")
async def generate_image(req: ImageGenRequest, user: dict = Depends(get_current_user)):
    job_id = f"img_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.image_jobs.insert_one({
        "id": job_id, "user_id": user["user_id"], "status": "processing",
        "image": None, "error": None, "created_at": now, "updated_at": now,
    })
    asyncio.create_task(_run_image_job(job_id, user["user_id"], req.prompt, req.client_id, req.gen_group_id))
    return {"job_id": job_id, "status": "processing"}

@api_router.get("/pieces/image-job/{job_id}")
async def image_job_status(job_id: str, user: dict = Depends(get_current_user)):
    job = await db.image_jobs.find_one({"id": job_id, "user_id": user["user_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado")
    status = job["status"]
    resp = {"status": status, "image": job.get("image"), "error": job.get("error"),
            "cost_brl": job.get("cost_brl"), "stage": job.get("stage")}
    if status in ("done", "error"):
        await db.image_jobs.delete_one({"id": job_id})
    return resp

@api_router.get("/pieces")
async def list_pieces(user: dict = Depends(get_current_user)):
    pieces = await db.pieces.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    pricing = await get_pricing(user["user_id"])
    mk = 1 + pricing["markup_pct"] / 100
    for p in pieces:
        if p.get("cost_brl") is not None:
            p["billable_brl"] = round(p["cost_brl"] * mk, 4)
    return pieces

@api_router.post("/pieces")
async def save_piece(req: PieceSaveRequest, user: dict = Depends(get_current_user)):
    doc = req.model_dump()
    doc.update({
        "id": f"pc_{uuid.uuid4().hex[:12]}", "user_id": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.pieces.insert_one(doc)
    await log_activity(user["user_id"], "peca", f"Peça salva: {req.title}")
    doc.pop("_id", None)
    if req.gen_group_id:
        uid = user["user_id"]
        await db.ai_costs.update_many(
            {"user_id": uid, "gen_group_id": req.gen_group_id, "piece_id": None},
            {"$set": {"piece_id": doc["id"], "client_id": req.client_id}},
        )
        costs = await db.ai_costs.find({"piece_id": doc["id"], "user_id": uid}, {"_id": 0}).to_list(100)
        total_brl = round(sum(c["cost_brl"] for c in costs), 4)
        regen = sum(1 for c in costs if c["stage"] in ("refacao_texto", "refacao_imagem"))
        breakdown = [{"stage": c["stage"], "label": STAGE_LABELS.get(c["stage"], c["stage"]),
                      "cost_brl": c["cost_brl"], "model": c["model"]} for c in costs]
        await db.pieces.update_one({"id": doc["id"]}, {"$set": {
            "gen_group_id": req.gen_group_id, "cost_brl": total_brl,
            "regen_count": regen, "cost_breakdown": breakdown,
        }})
        pricing = await get_pricing(uid)
        mk = 1 + pricing["markup_pct"] / 100
        doc.update({"cost_brl": total_brl, "regen_count": regen, "cost_breakdown": breakdown,
                    "billable_brl": round(total_brl * mk, 4)})
    return doc

@api_router.put("/pieces/{piece_id}")
async def update_piece(piece_id: str, req: PieceUpdateRequest, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    result = await db.pieces.update_one({"id": piece_id, "user_id": user["user_id"]}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Peça não encontrada")
    piece = await db.pieces.find_one({"id": piece_id}, {"_id": 0})
    if updates.get("status") == "aprovada":
        await log_activity(user["user_id"], "peca", f"Peça aprovada: {piece['title']}")
    return piece

def _parse_schedule(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Data de agendamento inválida")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

@api_router.post("/pieces/{piece_id}/publish")
async def publish_piece(piece_id: str, req: PublishRequest, user: dict = Depends(get_current_user)):
    piece = await db.pieces.find_one({"id": piece_id, "user_id": user["user_id"]}, {"_id": 0})
    if not piece:
        raise HTTPException(status_code=404, detail="Peça não encontrada")
    now = datetime.now(timezone.utc)
    scheduled = _parse_schedule(req.scheduled_at)
    if scheduled and scheduled > now:
        await db.pieces.update_one({"id": piece_id}, {"$set": {"status": "agendada", "scheduled_at": scheduled.isoformat(), "published_at": None}})
        await log_activity(user["user_id"], "publicacao", f"Peça agendada: {piece['title']} para {scheduled.strftime('%d/%m/%Y %H:%M')}")
    else:
        await db.pieces.update_one({"id": piece_id}, {"$set": {"status": "publicada", "published_at": now.isoformat(), "scheduled_at": None}})
        await log_activity(user["user_id"], "publicacao", f"Peça publicada: {piece['title']}")
    return await db.pieces.find_one({"id": piece_id}, {"_id": 0})

@api_router.delete("/pieces/{piece_id}")
async def delete_piece(piece_id: str, user: dict = Depends(get_current_user)):
    result = await db.pieces.delete_one({"id": piece_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Peça não encontrada")
    return {"message": "Peça removida"}

# ---------------- Bíblia (knowledge base) ----------------

@api_router.get("/bible/documents")
async def list_bible_docs(user: dict = Depends(get_current_user)):
    return await db.bible_documents.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)

@api_router.post("/bible/documents")
async def create_bible_doc(req: BibleDocCreate, user: dict = Depends(get_current_user)):
    doc = req.model_dump()
    doc.update({
        "id": f"doc_{uuid.uuid4().hex[:12]}", "user_id": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.bible_documents.insert_one(doc)
    await log_activity(user["user_id"], "biblia", f"Documento adicionado à Bíblia: {req.title}")
    doc.pop("_id", None)
    return doc

def _extract_text_from_file(filename: str, data: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "pdf":
        reader = pypdf.PdfReader(BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if ext == "docx":
        d = docx_lib.Document(BytesIO(data))
        return "\n".join(p.text for p in d.paragraphs if p.text)
    if ext == "xlsx":
        wb = openpyxl.load_workbook(BytesIO(data), read_only=True, data_only=True)
        parts = []
        for ws in wb.worksheets:
            parts.append(f"# Planilha: {ws.title}")
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) for c in row if c is not None]
                if cells:
                    parts.append(" | ".join(cells))
        return "\n".join(parts)
    if ext in ("txt", "md", "csv"):
        return data.decode("utf-8", errors="ignore")
    return ""

@api_router.post("/bible/upload")
async def upload_bible_doc(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: str = Form("Geral"),
    user: dict = Depends(get_current_user),
):
    filename = file.filename or "arquivo"
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    supported = {"pdf", "docx", "xlsx", "png", "jpg", "jpeg", "txt", "md", "csv"}
    if ext not in supported:
        raise HTTPException(status_code=400, detail="Formato não suportado. Use PDF, DOCX, XLSX, PNG, JPEG, TXT, CSV ou MD.")
    data = await file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (máx. 15MB).")

    is_image = ext in ("png", "jpg", "jpeg")
    raw_text = ""
    if not is_image:
        try:
            raw_text = _extract_text_from_file(filename, data)
        except Exception as e:
            logger.error(f"Falha ao extrair texto de {filename}: {e}")
            raise HTTPException(status_code=422, detail="Não foi possível ler o arquivo enviado.")

    system = (
        "Você organiza documentos para a base de conhecimento (Bíblia) de uma agência de marketing. "
        "Leia o material e produza um resumo estruturado em português do Brasil, pronto para servir de CONTEXTO para uma IA de criação. "
        "Inclua: visão geral, pontos-chave, tom de voz/diretrizes (se houver) e dados/números relevantes. "
        "Seja fiel ao conteúdo, não invente. Responda apenas com o texto do resumo, sem preâmbulos."
    )
    instruction = f"Nome do arquivo: {filename}\nCategoria: {category}\n\n"
    if is_image:
        b64 = base64.b64encode(data).decode()
        msg = UserMessage(
            text=instruction + "Extraia todo o texto visível e descreva o conteúdo desta imagem como contexto de marca/criativo.",
            file_contents=[ImageContent(image_base64=b64)],
        )
    else:
        excerpt = raw_text[:12000] if raw_text.strip() else "(sem texto extraível)"
        msg = UserMessage(text=instruction + f"Conteúdo extraído do documento:\n\n{excerpt}")

    context_text = ""
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"bible-upload-{uuid.uuid4().hex[:8]}",
            system_message=system,
        ).with_model("openai", "gpt-5.4-mini")
        parts = []
        async for ev in chat.stream_message(msg):
            if isinstance(ev, TextDelta):
                parts.append(ev.content)
            elif isinstance(ev, StreamDone):
                break
        context_text = "".join(parts).strip()
    except Exception as e:
        logger.error(f"Falha ao refinar anexo da Bíblia: {e}")
        context_text = raw_text.strip()

    if not context_text:
        raise HTTPException(status_code=422, detail="Não foi possível extrair conteúdo do arquivo.")

    doc = {
        "id": f"doc_{uuid.uuid4().hex[:12]}", "user_id": user["user_id"],
        "title": (title or "").strip() or filename.rsplit(".", 1)[0][:80],
        "category": category, "content": context_text, "source_file": filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.bible_documents.insert_one(doc)
    await log_activity(user["user_id"], "biblia", f"Anexo processado na Bíblia: {filename}")
    doc.pop("_id", None)
    return doc

@api_router.delete("/bible/documents/{doc_id}")
async def delete_bible_doc(doc_id: str, user: dict = Depends(get_current_user)):
    result = await db.bible_documents.delete_one({"id": doc_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    return {"message": "Documento removido"}

@api_router.post("/bible/ask")
async def bible_ask(req: BibleAskRequest, user: dict = Depends(get_current_user)):
    model_cfg = AI_MODELS.get(req.model, AI_MODELS["gpt-5.4-mini"])
    docs = await db.bible_documents.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(100)
    q_words = {w.lower() for w in req.question.split() if len(w) > 3}
    scored = []
    for d in docs:
        text = f"{d['title']} {d['content']}".lower()
        score = sum(1 for w in q_words if w in text)
        scored.append((score, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = [d for s, d in scored[:4] if s > 0] or docs[:3]
    context = "\n\n".join(f"### {d['title']} ({d['category']})\n{d['content'][:1200]}" for d in top)
    sources = [{"id": d["id"], "title": d["title"], "category": d["category"]} for d in top]
    system = (
        "Você é o oráculo da base de conhecimento (Bíblia) da agência. Responda em português do Brasil, "
        "de forma objetiva e útil, usando PRIORITARIAMENTE os documentos fornecidos. "
        "Se a resposta não estiver nos documentos, diga isso claramente antes de responder com conhecimento geral."
    )
    prompt = f"Documentos da Bíblia:\n{context if context else '(base vazia)'}\n\nPergunta: {req.question}"

    async def event_stream():
        try:
            yield f"data: {json.dumps({'sources': sources})}\n\n"
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"bible-{uuid.uuid4().hex[:8]}",
                system_message=system,
            ).with_model(model_cfg["provider"], model_cfg["model"])
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    yield f"data: {json.dumps({'delta': ev.content})}\n\n"
                elif isinstance(ev, StreamDone):
                    break
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.error(f"Erro na Bíblia: {e}")
            yield f"data: {json.dumps({'error': 'Falha ao consultar a Bíblia.'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

# ---------------- Campaigns (Meta Ads pilot, mock) ----------------

@api_router.get("/campaigns")
async def list_campaigns(user: dict = Depends(get_current_user)):
    campaigns = await db.campaigns.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    for c in campaigns:
        m = c.get("metrics", [])
        spend = sum(x["spend"] for x in m)
        clicks = sum(x["clicks"] for x in m)
        impressions = sum(x["impressions"] for x in m)
        conversions = sum(x["conversions"] for x in m)
        revenue = conversions * 87.5
        c["totals"] = {
            "spend": round(spend, 2), "clicks": clicks, "impressions": impressions,
            "conversions": conversions, "ctr": round(clicks / impressions * 100, 2) if impressions else 0,
            "roas": round(revenue / spend, 2) if spend else 0,
        }
        c.pop("metrics", None)
    return campaigns

@api_router.post("/campaigns")
async def create_campaign(req: CampaignCreate, user: dict = Depends(get_current_user)):
    client_doc = await db.clients.find_one({"id": req.client_id, "user_id": user["user_id"]}, {"_id": 0})
    if not client_doc:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    campaign_id = f"cmp_{uuid.uuid4().hex[:12]}"
    doc = req.model_dump()
    doc.update({
        "id": campaign_id, "user_id": user["user_id"], "platform": "meta",
        "client_name": client_doc["name"], "ad_account_id": f"act_{random.randint(10**9, 10**10 - 1)}",
        "metrics": campaign_metrics_series(campaign_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.campaigns.insert_one(doc)
    await log_activity(user["user_id"], "meta", f"Campanha criada (piloto Meta Ads): {req.name}")
    doc.pop("_id", None)
    return doc

@api_router.get("/campaigns/{campaign_id}/metrics")
async def campaign_metrics(campaign_id: str, user: dict = Depends(get_current_user)):
    c = await db.campaigns.find_one({"id": campaign_id, "user_id": user["user_id"]}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    return {"id": c["id"], "name": c["name"], "metrics": c.get("metrics", [])}

@api_router.post("/campaigns/{campaign_id}/sync")
async def sync_campaign(campaign_id: str, user: dict = Depends(get_current_user)):
    c = await db.campaigns.find_one({"id": campaign_id, "user_id": user["user_id"]}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    metrics = c.get("metrics", [])
    today = datetime.now(timezone.utc).date().isoformat()
    rng = random.Random(f"{campaign_id}-{today}-sync-{len(metrics)}")
    impressions = rng.randint(3000, 18000)
    clicks = int(impressions * rng.uniform(0.008, 0.035))
    new_day = {"date": today, "impressions": impressions, "clicks": clicks,
               "spend": round(rng.uniform(40, 220), 2), "conversions": int(clicks * rng.uniform(0.02, 0.12))}
    if metrics and metrics[-1]["date"] == today:
        metrics[-1] = new_day
    else:
        metrics.append(new_day)
    await db.campaigns.update_one({"id": campaign_id}, {"$set": {"metrics": metrics}})
    await log_activity(user["user_id"], "meta", f"Sincronização Meta Ads concluída: {c['name']}")
    await evaluate_alert_rules(user["user_id"])
    return {"message": "Sincronizado", "latest": new_day}

@api_router.post("/campaigns/{campaign_id}/status")
async def toggle_campaign_status(campaign_id: str, req: CampaignStatusUpdate, user: dict = Depends(get_current_user)):
    status = req.status
    if status not in ("ativa", "pausada", "em_analise"):
        raise HTTPException(status_code=400, detail="Status inválido")
    result = await db.campaigns.update_one({"id": campaign_id, "user_id": user["user_id"]}, {"$set": {"status": status}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    return {"message": "Status atualizado", "status": status}

@api_router.post("/campaigns/{campaign_id}/publish")
async def publish_campaign(campaign_id: str, req: PublishRequest, user: dict = Depends(get_current_user)):
    c = await db.campaigns.find_one({"id": campaign_id, "user_id": user["user_id"]}, {"_id": 0})
    if not c:
        raise HTTPException(status_code=404, detail="Campanha não encontrada")
    now = datetime.now(timezone.utc)
    scheduled = _parse_schedule(req.scheduled_at)
    if scheduled and scheduled > now:
        await db.campaigns.update_one({"id": campaign_id}, {"$set": {"status": "agendada", "scheduled_at": scheduled.isoformat(), "published_at": None}})
        await log_activity(user["user_id"], "publicacao", f"Campanha agendada: {c['name']} para {scheduled.strftime('%d/%m/%Y %H:%M')}")
    else:
        await db.campaigns.update_one({"id": campaign_id}, {"$set": {"status": "ativa", "published_at": now.isoformat(), "scheduled_at": None}})
        await log_activity(user["user_id"], "publicacao", f"Campanha publicada: {c['name']}")
    return await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})

# ---------------- Logs & alerts ----------------

@api_router.get("/logs")
async def list_logs(user: dict = Depends(get_current_user)):
    logs = await db.activity_logs.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    occurrences = await db.alert_occurrences.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"logs": logs, "occurrences": occurrences}

@api_router.get("/alerts/rules")
async def list_alert_rules(user: dict = Depends(get_current_user)):
    return await db.alert_rules.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(50)

@api_router.post("/alerts/rules")
async def create_alert_rule(req: AlertRuleCreate, user: dict = Depends(get_current_user)):
    if req.metric not in ("spend", "ctr", "roas", "conversions"):
        raise HTTPException(status_code=400, detail="Métrica inválida")
    if req.operator not in ("gt", "lt"):
        raise HTTPException(status_code=400, detail="Operador inválido")
    doc = req.model_dump()
    doc.update({"id": f"rule_{uuid.uuid4().hex[:12]}", "user_id": user["user_id"],
                "active": True, "created_at": datetime.now(timezone.utc).isoformat()})
    await db.alert_rules.insert_one(doc)
    await log_activity(user["user_id"], "alerta", f"Regra de alerta criada: {req.name}")
    doc.pop("_id", None)
    return doc

@api_router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule(rule_id: str, user: dict = Depends(get_current_user)):
    result = await db.alert_rules.delete_one({"id": rule_id, "user_id": user["user_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Regra não encontrada")
    return {"message": "Regra removida"}

async def evaluate_alert_rules(user_id: str):
    rules = await db.alert_rules.find({"user_id": user_id, "active": True}, {"_id": 0}).to_list(50)
    if not rules:
        return
    campaigns = await db.campaigns.find({"user_id": user_id}, {"_id": 0}).to_list(100)
    for rule in rules:
        for c in campaigns:
            m = c.get("metrics", [])
            if not m:
                continue
            spend = sum(x["spend"] for x in m)
            clicks = sum(x["clicks"] for x in m)
            impressions = sum(x["impressions"] for x in m)
            conversions = sum(x["conversions"] for x in m)
            values = {
                "spend": spend,
                "ctr": clicks / impressions * 100 if impressions else 0,
                "roas": (conversions * 87.5) / spend if spend else 0,
                "conversions": conversions,
            }
            value = values[rule["metric"]]
            triggered = value > rule["threshold"] if rule["operator"] == "gt" else value < rule["threshold"]
            if triggered:
                exists = await db.alert_occurrences.find_one({
                    "rule_id": rule["id"], "campaign_id": c["id"],
                    "created_at": {"$gt": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()},
                })
                if not exists:
                    await db.alert_occurrences.insert_one({
                        "id": f"occ_{uuid.uuid4().hex[:12]}", "user_id": user_id,
                        "rule_id": rule["id"], "rule_name": rule["name"],
                        "campaign_id": c["id"], "campaign_name": c["name"],
                        "metric": rule["metric"], "value": round(value, 2), "threshold": rule["threshold"],
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })

# ---------------- Settings (admin) ----------------

@api_router.get("/settings")
async def get_settings(user: dict = Depends(get_current_user)):
    s = await db.app_settings.find_one({"user_id": user["user_id"]}, {"_id": 0})
    if not s:
        s = {"user_id": user["user_id"], "default_model": "gpt-5.4-mini",
             "default_tone": "profissional", "agency_name": "", "meta_connected": False}
        await db.app_settings.insert_one(dict(s))
    s["available_models"] = [{"id": k, **{kk: vv for kk, vv in v.items() if kk != "provider"}} for k, v in AI_MODELS.items()]
    s["pricing"] = _merge_pricing(s.get("pricing"))
    return s

@api_router.put("/settings")
async def update_settings(req: SettingsUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "default_model" in updates and updates["default_model"] not in AI_MODELS:
        raise HTTPException(status_code=400, detail="Modelo inválido")
    await db.app_settings.update_one({"user_id": user["user_id"]}, {"$set": updates}, upsert=True)
    await log_activity(user["user_id"], "config", "Configurações atualizadas")
    return await db.app_settings.find_one({"user_id": user["user_id"]}, {"_id": 0})

@api_router.get("/reports/costs")
async def cost_report(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    pricing = await get_pricing(uid)
    mk = 1 + pricing["markup_pct"] / 100
    costs = await db.ai_costs.find({"user_id": uid}, {"_id": 0}).to_list(50000)
    clients = {c["id"]: c["name"] for c in await db.clients.find({"user_id": uid}, {"_id": 0, "id": 1, "name": 1}).to_list(1000)}
    agg = {}
    for c in costs:
        key = c.get("client_id") or "none"
        a = agg.setdefault(key, {"client_id": key, "client_name": clients.get(c.get("client_id"), "Sem cliente"),
                                 "cost_brl": 0.0, "pieces": set(), "stages": 0, "refacoes": 0})
        a["cost_brl"] += c["cost_brl"]
        if c.get("piece_id"):
            a["pieces"].add(c["piece_id"])
        a["stages"] += 1
        if c["stage"] in ("refacao_texto", "refacao_imagem"):
            a["refacoes"] += 1
    rows = [{"client_id": a["client_id"], "client_name": a["client_name"],
             "cost_brl": round(a["cost_brl"], 4), "billable_brl": round(a["cost_brl"] * mk, 4),
             "pieces": len(a["pieces"]), "refacoes": a["refacoes"], "stages": a["stages"]}
            for a in agg.values()]
    rows.sort(key=lambda x: -x["cost_brl"])
    total_cost = round(sum(r["cost_brl"] for r in rows), 4)
    return {"rows": rows, "total_cost_brl": total_cost, "total_billable_brl": round(total_cost * mk, 4),
            "markup_pct": pricing["markup_pct"]}

# ---------------- Email (Resend gerenciado) ----------------
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
EMAIL_KEY = os.environ.get("EMERGENT_EMAIL_KEY")
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Vanguarda.IA")
EMAIL_REPLY_TO = os.environ.get("EMAIL_REPLY_TO")

_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)

def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)

def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)

class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []
    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []

def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} != real link host {real!r} (G3)")

async def send_email(*, to: str, subject: str, html: str, reply_to: Optional[str] = None) -> Optional[str]:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": EMAIL_FROM_NAME}
    if reply_to or EMAIL_REPLY_TO:
        payload["contact_email"] = reply_to or EMAIL_REPLY_TO
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send",
                                     headers={"X-Email-Key": EMAIL_KEY}, json=payload)
        resp.raise_for_status()
        return resp.json().get("id")
    except httpx.HTTPStatusError as e:
        logger.error(f"Email send failed: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=502, detail="Falha ao enviar e-mail")
    except Exception as e:
        logger.error(f"Email send error: {str(e)}")
        raise HTTPException(status_code=500, detail="Falha ao enviar e-mail")

# ---------------- Agentes operacionais (human-in-the-loop) ----------------
AGENTS = {
    "social": {"label": "Social Media", "sector": "Social", "icon": "share-2",
               "desc": "Plano de social com estratégia, tendências, cronograma, prazos, custos, copy e briefing de arte.", "action": "Aprovar cria as peças (rascunho) já com datas e briefs."},
    "inbound": {"label": "Inbound / Conteúdo", "sector": "Inbound", "icon": "magnet",
                "desc": "Plano de conteúdo por funil e SEO com cronograma, prazos de redação e custos.", "action": "Aprovar cria os artigos (rascunho) com outline e capa."},
    "midia_paga": {"label": "Mídia Paga", "sector": "Mídia Paga", "icon": "target",
                   "desc": "Plano de mídia por funil com orçamento, cronograma, públicos, criativos e metas.", "action": "Aprovar cria a(s) campanha(s) com datas e verba."},
    "account": {"label": "Account / Atendimento", "sector": "Account", "icon": "mail",
                "desc": "Relatório de performance redigido para o cliente.", "action": "Aprovar envia o e-mail ao cliente."},
    "otimizacao": {"label": "Otimização de Performance", "sector": "Mídia Paga", "icon": "trending-up",
                   "desc": "Lê métricas e recomenda pausar/escalar/ajustar campanhas.", "action": "Aprovar aplica as ações nas campanhas."},
}

class AgentRunRequest(BaseModel):
    client_id: str
    model: str = "claude-sonnet-4-6"
    instructions: str = ""
    quantity: int = 5

def _parse_agent_json(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("resposta sem JSON")
    return json.loads(m.group(0))

async def run_agent_llm(user_id, model, system, user_prompt, client_id=None):
    if model not in AI_MODELS:
        model = "claude-sonnet-4-6"
    cfg = AI_MODELS[model]
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=f"agent-{uuid.uuid4().hex[:8]}",
                   system_message=system).with_model(cfg["provider"], cfg["model"])
    parts = []; itok = otok = 0
    async for ev in chat.stream_message(UserMessage(text=user_prompt)):
        if isinstance(ev, TextDelta):
            parts.append(ev.content)
        elif isinstance(ev, StreamDone):
            if ev.usage:
                itok = ev.usage.input_tokens or 0
                otok = ev.usage.output_tokens or 0
            break
    cost = await record_cost(user_id, None, "agente", model, itok, otok, client_id=client_id)
    return "".join(parts).strip(), cost["cost_brl"]

async def _metrics_summary(user_id, client_id) -> str:
    camps = await db.campaigns.find({"user_id": user_id, "client_id": client_id}, {"_id": 0}).to_list(50)
    if not camps:
        return "Sem campanhas ativas/registradas para este cliente."
    lines = []
    for c in camps:
        ms = c.get("metrics", [])[-30:]
        spend = sum(m["spend"] for m in ms); imp = sum(m["impressions"] for m in ms)
        clk = sum(m["clicks"] for m in ms); conv = sum(m["conversions"] for m in ms)
        ctr = round((clk / imp) * 100, 2) if imp else 0
        lines.append(f"- {c['name']} ({c.get('status')}): invest R${spend:.0f}, {imp} impressões, CTR {ctr}%, {conv} conversões")
    return "\n".join(lines)

def _media_total(camps) -> float:
    return sum(_num(c.get("budget_daily")) * (_num(c.get("duracao_dias")) or 30) for c in camps)

def _proposal_view(agent_key, client_name, payload) -> dict:
    """Monta título, resumo e texto do plano a partir do payload (usado na geração e na edição)."""
    if agent_key == "social":
        posts = payload.get("posts", []); total = _num(payload.get("custo_total"))
        lines = [f"Estratégia: {payload.get('estrategia', '')}",
                 f"Período: {payload.get('periodo') or '—'}  |  Custo estimado: R${total:.0f}", ""]
        for p in posts:
            lines.append(f"- {p.get('data_publicacao', '—')} [{p.get('formato')}] {p.get('titulo')}")
            lines.append(f"    Pilar {p.get('pilar', '—')} · Tendência: {p.get('tendencia', '—')} · Prazo arte {p.get('prazo_arte', '—')} · R${_num(p.get('custo_estimado')):.0f}")
            lines.append(f"    Arte: {p.get('brief_arte', '—')}")
        if payload.get("kpis"):
            lines.append("\nKPIs: " + ", ".join(payload["kpis"]))
        return {"title": f"Plano social — {client_name} ({len(posts)} posts)",
                "summary": f"{len(posts)} posts · R${total:.0f} · {payload.get('periodo', '')}",
                "preview": "\n".join(lines)}
    if agent_key == "inbound":
        arts = payload.get("articles", []); total = _num(payload.get("custo_total"))
        lines = [f"Estratégia: {payload.get('estrategia', '')}", f"Custo estimado: R${total:.0f}", ""]
        for a in arts:
            lines.append(f"- [{a.get('etapa_funil', '—')}] {a.get('titulo')}")
            lines.append(f"    Palavra-chave: {a.get('palavra_chave', '—')} ({a.get('intencao_busca', '—')}) · Publicar {a.get('data_publicacao', '—')} · Prazo redação {a.get('prazo_redacao', '—')} · R${_num(a.get('custo_estimado')):.0f}")
        if payload.get("kpis"):
            lines.append("\nKPIs: " + ", ".join(payload["kpis"]))
        return {"title": f"Plano inbound — {client_name} ({len(arts)} artigos)",
                "summary": f"{len(arts)} artigos · R${total:.0f}",
                "preview": "\n".join(lines)}
    if agent_key == "midia_paga":
        camps = payload.get("campaigns", []); total_inv = _num(payload.get("investimento_total"))
        lines = [f"Estratégia: {payload.get('estrategia', '')}", f"Investimento total estimado: R${total_inv:.0f}", ""]
        for c in camps:
            lines.append(f"- {c.get('name')} [{c.get('objetivo_funil', '—')} · {c.get('objective', '—')}]")
            lines.append(f"    R${_num(c.get('budget_daily')):.0f}/dia · {c.get('duracao_dias', '—')} dias ({c.get('data_inicio', '—')} a {c.get('data_fim', '—')}) · Meta: {c.get('kpi_alvo', '—')}")
            lines.append(f"    Público: {c.get('audience', '—')}")
            lines.append(f"    Criativo: {c.get('brief_criativo', '—')}")
        return {"title": f"Plano de mídia — {client_name} ({len(camps)} campanhas)",
                "summary": f"{len(camps)} campanha(s) · R${total_inv:.0f} total",
                "preview": "\n".join(lines)}
    if agent_key == "account":
        subject = payload.get("subject") or f"Relatório de performance — {client_name}"
        preview = f"Para: {payload.get('to_email') or '(sem e-mail)'}\nAssunto: {subject}\n\n{(payload.get('report_text') or '')[:600]}"
        return {"title": f"Relatório ao cliente — {client_name}", "summary": subject, "preview": preview}
    raise HTTPException(status_code=400, detail="Este tipo de proposta não pode ser editado")

# Campos editáveis por agente: (chave da lista de itens, campos de cada item, campos gerais do plano).
# Tipos: "s" texto, "n" número, "l" lista de textos.
PROPOSAL_EDIT_SCHEMA = {
    "social": ("posts",
               {"data_publicacao": "s", "prazo_arte": "s", "formato": "s", "pilar": "s", "tendencia": "s", "titulo": "s",
                "legenda": "s", "hashtags": "l", "cta": "s", "brief_arte": "s", "custo_estimado": "n"},
               {"estrategia": "s", "periodo": "s", "kpis": "l"}),
    "inbound": ("articles",
                {"titulo": "s", "etapa_funil": "s", "palavra_chave": "s", "keywords": "l", "intencao_busca": "s",
                 "data_publicacao": "s", "prazo_redacao": "s", "outline": "s", "cta": "s", "brief_arte": "s", "custo_estimado": "n"},
                {"estrategia": "s", "kpis": "l"}),
    "midia_paga": ("campaigns",
                   {"name": "s", "objetivo_funil": "s", "objective": "s", "budget_daily": "n", "duracao_dias": "n",
                    "data_inicio": "s", "data_fim": "s", "audience": "s", "angles": "l", "brief_criativo": "s",
                    "kpi_alvo": "s", "resultado_esperado": "s"},
                   {"estrategia": "s"}),
    "account": (None, {}, {"subject": "s", "report_text": "s", "to_email": "s"}),
}
PLAN_AGENTS = ("social", "inbound", "midia_paga")  # só estes podem ser editados depois de aprovados
MAX_PLAN_ITEMS = 10

def _clean_field(kind, v):
    if kind == "n":
        return max(0.0, _num(v))
    if kind == "l":
        items = v if isinstance(v, list) else re.split(r"[,\n]", str(v or ""))
        return [str(x).strip()[:200] for x in items if str(x).strip()][:30]
    return "" if v is None else str(v).strip()[:8000]

def _sanitize_proposal_payload(agent_key, original: dict, incoming) -> dict:
    """Aceita só os campos conhecidos, com tipos corretos, e recalcula os totais."""
    if agent_key not in PROPOSAL_EDIT_SCHEMA:
        raise HTTPException(status_code=400, detail="Este tipo de proposta não pode ser editado")
    if not isinstance(incoming, dict):
        raise HTTPException(status_code=400, detail="Dados do plano inválidos")
    list_key, item_fields, top_fields = PROPOSAL_EDIT_SCHEMA[agent_key]
    payload = dict(original or {})
    for f, kind in top_fields.items():
        if f in incoming:
            payload[f] = _clean_field(kind, incoming[f])
    if list_key:
        raw_items = incoming.get(list_key, payload.get(list_key, []))
        if not isinstance(raw_items, list):
            raise HTTPException(status_code=400, detail="Lista de itens inválida")
        if len(raw_items) > MAX_PLAN_ITEMS:
            raise HTTPException(status_code=400, detail=f"Máximo de {MAX_PLAN_ITEMS} itens por plano")
        payload[list_key] = [{f: _clean_field(kind, it.get(f)) for f, kind in item_fields.items()}
                             for it in raw_items if isinstance(it, dict)]
        if agent_key == "midia_paga":
            for c in payload[list_key]:
                c["duracao_dias"] = int(c["duracao_dias"]) or 30
            payload["investimento_total"] = _media_total(payload[list_key])
        else:
            payload["custo_total"] = sum(it["custo_estimado"] for it in payload[list_key])
    if agent_key == "account" and payload.get("to_email") and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", payload["to_email"]):
        raise HTTPException(status_code=400, detail="E-mail do destinatário inválido")
    return payload

async def _agent_generate(agent_key, user, client, req: AgentRunRequest):
    uid = user["user_id"]
    context = await build_brand_context(uid, client["id"])
    base_ctx = f"Cliente: {client['name']} (segmento: {client.get('segment', 'n/d')}).\nContexto da marca (Bíblia):\n{context}\n"
    instr = f"Instruções extras do usuário: {req.instructions}\n" if req.instructions else ""
    q = max(1, min(int(req.quantity or 5), 10))
    hoje = datetime.now(timezone.utc).date().isoformat()

    if agent_key == "social":
        system = ("Você é Head de Social Media de uma agência brasileira premium. Domina tendências ATUAIS (Reels curtos, storytelling, UGC, "
                  "social commerce, carrosséis salváveis, IA generativa) e traduz isso em resultado. Entrega planos acionáveis com cronograma, "
                  "prazos de produção, custos e briefing de arte. Responda SOMENTE com JSON válido, sem texto fora do JSON.")
        prompt = (base_ctx + instr + f"Data de hoje: {hoje}. Monte um PLANO de social media com {q} publicações em pt-BR, distribuídas em DATAS REAIS a partir de hoje, "
                  "aplicando tendências atuais de mercado ao segmento do cliente. Cada item deve ter copy pronta para publicar e um briefing de arte detalhado. "
                  'Retorne JSON: {"estrategia":"resumo estratégico em 2-3 frases citando as tendências aplicadas","periodo":"ex: 10 a 24/06",'
                  '"posts":[{"data_publicacao":"AAAA-MM-DD","prazo_arte":"AAAA-MM-DD","formato":"post_instagram|stories|reel|carrossel|anuncio_meta",'
                  '"pilar":"Autoridade|Conexão|Conversão|Educação","tendencia":"tendência de mercado aplicada","titulo":"título curto",'
                  '"legenda":"legenda pronta, persuasiva, em pt-BR, com quebras de linha e emojis quando fizer sentido","hashtags":["#..."],'
                  '"cta":"chamada para ação","brief_arte":"descrição visual detalhada para o designer/IA gerar a arte (cena, estilo, cores, texto na peça)",'
                  '"custo_estimado":80}],"custo_total":0,"kpis":["métricas de sucesso"]}')
        data = _parse_agent_json((await run_agent_llm(uid, req.model, system, prompt, client["id"]))[0])
        posts = data.get("posts", [])[:q]
        total = _num(data.get("custo_total")) or sum(_num(p.get("custo_estimado")) for p in posts)
        payload = {"posts": posts, "estrategia": data.get("estrategia", ""), "periodo": data.get("periodo", ""), "custo_total": total, "kpis": data.get("kpis", [])}
        return {**_proposal_view("social", client["name"], payload), "payload": payload}

    if agent_key == "inbound":
        system = ("Você é Head de Inbound & SEO de uma agência brasileira. Domina SEO atual (intenção de busca, EEAT, topic clusters, "
                  "featured snippets), estratégia de funil e nutrição de leads. Responda SOMENTE com JSON válido.")
        prompt = (base_ctx + instr + f"Data de hoje: {hoje}. Proponha {min(q, 4)} conteúdos de blog em pt-BR com estratégia de FUNIL e SEO, com cronograma, prazos e custos. "
                  'Retorne JSON: {"estrategia":"resumo da estratégia de inbound e tendências aplicadas",'
                  '"articles":[{"titulo":"título otimizado para SEO","etapa_funil":"Topo|Meio|Fundo","palavra_chave":"palavra-chave principal",'
                  '"keywords":["secundárias"],"intencao_busca":"informacional|comercial|transacional","data_publicacao":"AAAA-MM-DD","prazo_redacao":"AAAA-MM-DD",'
                  '"outline":"H2/H3 do artigo separados por novas linhas","cta":"chamada para ação","brief_arte":"imagem de capa sugerida","custo_estimado":150}],'
                  '"custo_total":0,"kpis":["métricas de sucesso"]}')
        data = _parse_agent_json((await run_agent_llm(uid, req.model, system, prompt, client["id"]))[0])
        arts = data.get("articles", [])[:4]
        total = _num(data.get("custo_total")) or sum(_num(a.get("custo_estimado")) for a in arts)
        payload = {"articles": arts, "estrategia": data.get("estrategia", ""), "custo_total": total, "kpis": data.get("kpis", [])}
        return {**_proposal_view("inbound", client["name"], payload), "payload": payload}

    if agent_key == "midia_paga":
        system = ("Você é Head de Mídia Paga (Meta/Google Ads) de uma agência brasileira. Estrutura campanhas por funil (topo/meio/fundo), "
                  "com públicos, criativos, cronograma, orçamento e metas, usando tendências atuais (Advantage+, criativos em vídeo/UGC). "
                  "Responda SOMENTE com JSON válido.")
        prompt = (base_ctx + instr + f"Data de hoje: {hoje}. Monte um PLANO DE MÍDIA com 1 a 3 campanhas Meta Ads em pt-BR, cobrindo o funil, com orçamento, "
                  "cronograma (datas de início/fim), públicos, briefing de criativo e metas de performance. "
                  'Retorne JSON: {"estrategia":"visão geral do funil e das tendências aplicadas","campaigns":[{"name":"nome da campanha",'
                  '"objetivo_funil":"Topo|Meio|Fundo","objective":"Reconhecimento|Tráfego|Conversões|Leads|Remarketing","budget_daily":100,"duracao_dias":30,'
                  '"data_inicio":"AAAA-MM-DD","data_fim":"AAAA-MM-DD","audience":"segmentação detalhada (interesses, lookalike, remarketing)",'
                  '"angles":["ângulos criativos"],"brief_criativo":"descrição do criativo/arte a produzir","kpi_alvo":"ex: CPA < R$30 / ROAS > 3",'
                  '"resultado_esperado":"estimativa de resultado"}],"investimento_total":0}')
        data = _parse_agent_json((await run_agent_llm(uid, req.model, system, prompt, client["id"]))[0])
        camps = data.get("campaigns", [])[:3]
        total_inv = _num(data.get("investimento_total")) or _media_total(camps)
        payload = {"campaigns": camps, "estrategia": data.get("estrategia", ""), "investimento_total": total_inv}
        return {**_proposal_view("midia_paga", client["name"], payload), "payload": payload}

    if agent_key == "account":
        metrics = await _metrics_summary(uid, client["id"])
        system = "Você é account/atendimento sênior de uma agência brasileira. Escreva um relatório claro e cordial em pt-BR. Responda SOMENTE com JSON válido."
        prompt = (base_ctx + instr + f"Métricas recentes:\n{metrics}\n\n"
                  "Escreva um relatório de performance para o cliente (texto corrido, sem HTML, sem pedir senhas/dados sensíveis). "
                  'Retorne JSON: {"subject":"assunto do e-mail","report_text":"corpo do relatório em pt-BR"}')
        data = _parse_agent_json((await run_agent_llm(uid, req.model, system, prompt, client["id"]))[0])
        subject = data.get("subject", f"Relatório de performance — {client['name']}")
        payload = {"subject": subject, "report_text": data.get("report_text", ""), "to_email": client.get("contact_email", "")}
        return {**_proposal_view("account", client["name"], payload), "payload": payload}

    if agent_key == "otimizacao":
        camps = await db.campaigns.find({"user_id": uid, "client_id": client["id"]}, {"_id": 0}).to_list(50)
        if not camps:
            raise HTTPException(status_code=400, detail="Cliente sem campanhas para otimizar.")
        lines = []
        for c in camps:
            ms = c.get("metrics", [])[-14:]
            spend = sum(m["spend"] for m in ms); imp = sum(m["impressions"] for m in ms)
            clk = sum(m["clicks"] for m in ms); conv = sum(m["conversions"] for m in ms)
            ctr = round((clk / imp) * 100, 2) if imp else 0
            cpa = round(spend / conv, 2) if conv else 0
            lines.append(f'id={c["id"]} | {c["name"]} | status={c.get("status")} | budget=R${c.get("budget_daily")}/dia | invest14d=R${spend:.0f} | CTR={ctr}% | conv={conv} | CPA=R${cpa}')
        system = "Você é gestor de tráfego pago (Meta Ads) sênior. Analise as campanhas e recomende ações objetivas. Responda SOMENTE com JSON válido."
        prompt = (base_ctx + instr + "Campanhas do cliente (use EXATAMENTE o campaign_id fornecido):\n" + "\n".join(lines) +
                  '\n\nRetorne JSON: {"actions":[{"campaign_id":"id exato da lista","campaign_name":"...","recommendation":"pausar|ativar|escalar|reduzir","reason":"motivo curto em pt-BR","budget_new":número ou null}]}. '
                  "Recomende: pausar campanhas com desperdício (CTR baixo e CPA alto sem conversões); escalar (aumentar budget) as de melhor desempenho; reduzir as ineficientes; ativar pausadas promissoras. Só inclua ações que valem a pena.")
        data = _parse_agent_json((await run_agent_llm(uid, req.model, system, prompt, client["id"]))[0])
        valid = {c["id"] for c in camps}
        actions = [a for a in data.get("actions", []) if a.get("campaign_id") in valid][:10]
        lbl = {"pausar": "Pausar", "ativar": "Ativar", "escalar": "Escalar budget", "reduzir": "Reduzir budget"}
        preview = "\n".join(
            f'• {a.get("campaign_name")}: {lbl.get(a.get("recommendation"), a.get("recommendation"))}'
            + (f' → R${a.get("budget_new")}/dia' if a.get("budget_new") else "")
            + f'\n   ↳ {a.get("reason", "")}' for a in actions)
        return {"title": f"Otimização — {client['name']} ({len(actions)} ações)", "summary": f"{len(actions)} recomendação(ões)", "preview": preview, "payload": {"actions": actions}}

    raise HTTPException(status_code=400, detail="Agente inválido")

@api_router.get("/agents")
async def list_agents(user: dict = Depends(get_current_user)):
    return [{"key": k, **v} for k, v in AGENTS.items()]

@api_router.post("/agents/{agent_key}/run")
async def run_agent(agent_key: str, req: AgentRunRequest, user: dict = Depends(get_current_user)):
    if agent_key not in AGENTS:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    client = await db.clients.find_one({"id": req.client_id, "user_id": user["user_id"]}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    try:
        gen = await _agent_generate(agent_key, user, client, req)
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="O agente não retornou um resultado válido. Tente novamente.")
    prop = {
        "id": f"prop_{uuid.uuid4().hex[:12]}", "user_id": user["user_id"], "agent_key": agent_key,
        "agent_label": AGENTS[agent_key]["label"], "client_id": req.client_id, "client_name": client["name"],
        "model": req.model, "status": "pendente", "title": gen["title"], "summary": gen["summary"],
        "preview": gen["preview"], "payload": gen["payload"], "result": None,
        "created_at": datetime.now(timezone.utc).isoformat(), "decided_at": None,
    }
    await db.agent_proposals.insert_one(prop)
    await log_activity(user["user_id"], "agente", f"Agente {AGENTS[agent_key]['label']} gerou proposta para {client['name']}")
    prop.pop("_id", None)
    return prop

@api_router.get("/agents/proposals")
async def list_proposals(status: Optional[str] = None, user: dict = Depends(get_current_user)):
    q = {"user_id": user["user_id"]}
    if status:
        q["status"] = status
    return await db.agent_proposals.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)

@api_router.put("/agents/proposals/{prop_id}")
async def update_proposal(prop_id: str, body: dict, user: dict = Depends(get_current_user)):
    p = await db.agent_proposals.find_one({"id": prop_id, "user_id": user["user_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    # Pendente: a edição muda o que será criado na aprovação.
    # Aprovado (só planos): atualiza o registro do plano; campanhas/peças já criadas não mudam.
    editable = p["status"] == "pendente" or (p["status"] == "aprovado" and p["agent_key"] in PLAN_AGENTS)
    if not editable:
        raise HTTPException(status_code=400, detail="Esta proposta não pode mais ser editada")
    if body.get("payload") is None:
        raise HTTPException(status_code=400, detail="Nada para salvar")
    payload = _sanitize_proposal_payload(p["agent_key"], p.get("payload"), body["payload"])
    view = _proposal_view(p["agent_key"], p["client_name"], payload)
    await db.agent_proposals.update_one({"id": prop_id}, {"$set": {
        "payload": payload, **view, "edited_at": datetime.now(timezone.utc).isoformat()}})
    await log_activity(user["user_id"], "agente", f"Proposta editada: {view['title']}")
    return await db.agent_proposals.find_one({"id": prop_id}, {"_id": 0})

async def _apply_proposal(p, user):
    uid = user["user_id"]; key = p["agent_key"]; payload = p["payload"]; now = datetime.now(timezone.utc).isoformat()
    if key == "social":
        n = 0
        for post in payload.get("posts", []):
            fmt = post.get("formato") if post.get("formato") in PIECE_TYPES else "post_instagram"
            parts = [(post.get("legenda") or "").strip()]
            tags = post.get("hashtags") or []
            if tags:
                parts.append(" ".join(tags))
            if post.get("cta"):
                parts.append(f"CTA: {post.get('cta')}")
            if post.get("brief_arte"):
                parts.append(f"Brief de arte: {post.get('brief_arte')}")
            meta = []
            if post.get("pilar"):
                meta.append(f"Pilar: {post.get('pilar')}")
            if post.get("tendencia"):
                meta.append(f"Tendência: {post.get('tendencia')}")
            if post.get("prazo_arte"):
                meta.append(f"Prazo arte: {post.get('prazo_arte')}")
            if meta:
                parts.append(" · ".join(meta))
            dp = post.get("data_publicacao")
            scheduled = f"{dp}T12:00:00+00:00" if dp and re.match(r"^\d{4}-\d{2}-\d{2}$", str(dp)) else None
            await db.pieces.insert_one({
                "id": f"pc_{uuid.uuid4().hex[:12]}", "user_id": uid, "client_id": p["client_id"],
                "title": post.get("titulo") or "Post", "piece_type": fmt, "model": p["model"],
                "prompt": post.get("brief_arte") or "Gerado pelo agente Social", "content": "\n\n".join([x for x in parts if x]),
                "image": None, "status": "rascunho", "scheduled_at": scheduled,
                "created_at": now, "source_agent": "social",
            })
            n += 1
        return {"created_pieces": n}
    if key == "inbound":
        n = 0
        for a in payload.get("articles", []):
            content = (f"{a.get('titulo', '')}\n\nEtapa do funil: {a.get('etapa_funil', '—')}\n"
                       f"Palavra-chave: {a.get('palavra_chave', '—')} ({a.get('intencao_busca', '—')})\n"
                       f"Keywords: {', '.join(a.get('keywords', []))}\n\n{a.get('outline', '')}\n\n"
                       f"CTA: {a.get('cta', '')}\nBrief de capa: {a.get('brief_arte', '')}")
            dp = a.get("data_publicacao")
            scheduled = f"{dp}T12:00:00+00:00" if dp and re.match(r"^\d{4}-\d{2}-\d{2}$", str(dp)) else None
            await db.pieces.insert_one({
                "id": f"pc_{uuid.uuid4().hex[:12]}", "user_id": uid, "client_id": p["client_id"],
                "title": a.get("titulo") or "Artigo", "piece_type": "blog", "model": p["model"],
                "prompt": a.get("brief_arte") or "Gerado pelo agente Inbound", "content": content,
                "image": None, "status": "rascunho", "scheduled_at": scheduled,
                "created_at": now, "source_agent": "inbound",
            })
            n += 1
        return {"created_pieces": n}
    if key == "midia_paga":
        client = await db.clients.find_one({"id": p["client_id"], "user_id": uid}, {"_id": 0})
        n = 0
        for c in payload.get("campaigns", []):
            cid = f"cmp_{uuid.uuid4().hex[:12]}"
            budget = _num(c.get("budget_daily")) or 100.0
            await db.campaigns.insert_one({
                "id": cid, "user_id": uid, "client_id": p["client_id"], "platform": "meta",
                "client_name": client["name"] if client else p["client_name"],
                "name": c.get("name") or "Campanha", "objective": c.get("objective") or "Conversões",
                "objetivo_funil": c.get("objetivo_funil", ""), "budget_daily": budget, "status": "ativa",
                "duracao_dias": c.get("duracao_dias"), "data_inicio": c.get("data_inicio"), "data_fim": c.get("data_fim"),
                "audience": c.get("audience", ""), "angles": c.get("angles", []),
                "brief_criativo": c.get("brief_criativo", ""), "kpi_alvo": c.get("kpi_alvo", ""),
                "resultado_esperado": c.get("resultado_esperado", ""),
                "ad_account_id": f"act_{random.randint(10**9, 10**10 - 1)}",
                "metrics": campaign_metrics_series(cid), "created_at": now,
            })
            n += 1
        return {"created_campaigns": n}
    if key == "account":
        to = (payload.get("to_email") or "").strip()
        if not to:
            raise HTTPException(status_code=400, detail="Cliente sem e-mail de contato para enviar o relatório.")
        subject = payload.get("subject") or f"Relatório de performance — {p['client_name']}"
        safe = escape(payload.get("report_text", "")).replace("\n", "<br>")
        html = (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#111">'
                f'<p>{safe}</p>'
                f'<p style="font-size:12px;color:#888">Enviado por {escape(EMAIL_FROM_NAME)}. Nunca pedimos senha ou dados de cartão por e-mail.</p>'
                f'</td></tr></table>')
    if key == "otimizacao":
        applied = 0
        for a in payload.get("actions", []):
            cid = a.get("campaign_id"); rec = a.get("recommendation"); upd = {}
            if rec == "pausar":
                upd["status"] = "pausada"
            elif rec == "ativar":
                upd["status"] = "ativa"
            elif rec in ("escalar", "reduzir"):
                bn = a.get("budget_new")
                if bn:
                    try:
                        upd["budget_daily"] = float(bn)
                    except (TypeError, ValueError):
                        pass
                if "budget_daily" not in upd:
                    c = await db.campaigns.find_one({"id": cid, "user_id": uid}, {"_id": 0, "budget_daily": 1})
                    if c:
                        cur = float(c.get("budget_daily") or 100)
                        upd["budget_daily"] = round(cur * (1.2 if rec == "escalar" else 0.8), 2)
            if upd:
                r = await db.campaigns.update_one({"id": cid, "user_id": uid}, {"$set": upd})
                if r.matched_count:
                    applied += 1
        return {"optimized_campaigns": applied}
    raise HTTPException(status_code=400, detail="Agente inválido")

@api_router.post("/agents/proposals/{prop_id}/approve")
async def approve_proposal(prop_id: str, user: dict = Depends(get_current_user)):
    p = await db.agent_proposals.find_one({"id": prop_id, "user_id": user["user_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    if p["status"] != "pendente":
        raise HTTPException(status_code=400, detail="Proposta já decidida")
    result = await _apply_proposal(p, user)
    await db.agent_proposals.update_one({"id": prop_id}, {"$set": {
        "status": "aprovado", "result": result, "decided_at": datetime.now(timezone.utc).isoformat()}})
    await log_activity(user["user_id"], "agente", f"Proposta aprovada e executada: {p['title']}")
    return await db.agent_proposals.find_one({"id": prop_id}, {"_id": 0})

@api_router.post("/agents/proposals/{prop_id}/reject")
async def reject_proposal(prop_id: str, user: dict = Depends(get_current_user)):
    p = await db.agent_proposals.find_one({"id": prop_id, "user_id": user["user_id"]}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    await db.agent_proposals.update_one({"id": prop_id}, {"$set": {
        "status": "rejeitado", "decided_at": datetime.now(timezone.utc).isoformat()}})
    return {"message": "Proposta rejeitada"}

@api_router.delete("/agents/proposals/{prop_id}")
async def delete_proposal(prop_id: str, user: dict = Depends(get_current_user)):
    r = await db.agent_proposals.delete_one({"id": prop_id, "user_id": user["user_id"]})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    return {"message": "Proposta removida"}

class BulkAction(BaseModel):
    ids: List[str]
    action: str  # approve | reject

@api_router.post("/agents/proposals/bulk")
async def bulk_proposals(body: BulkAction, user: dict = Depends(get_current_user)):
    approved = rejected = errors = 0
    for pid in body.ids:
        p = await db.agent_proposals.find_one({"id": pid, "user_id": user["user_id"]}, {"_id": 0})
        if not p or p["status"] != "pendente":
            errors += 1
            continue
        try:
            if body.action == "approve":
                result = await _apply_proposal(p, user)
                await db.agent_proposals.update_one({"id": pid}, {"$set": {"status": "aprovado", "result": result, "decided_at": datetime.now(timezone.utc).isoformat()}})
                approved += 1
            else:
                await db.agent_proposals.update_one({"id": pid}, {"$set": {"status": "rejeitado", "decided_at": datetime.now(timezone.utc).isoformat()}})
                rejected += 1
        except Exception as e:
            logger.error(f"Bulk {body.action} falhou para {pid}: {e}")
            errors += 1
    return {"approved": approved, "rejected": rejected, "errors": errors}

# ---------------- Agendamentos de agentes ----------------
class AgentScheduleCreate(BaseModel):
    agent_key: str
    client_id: str
    model: str = "claude-sonnet-4-6"
    instructions: str = ""
    quantity: int = 5
    frequency: str = "weekly"  # daily | weekly
    weekday: int = 1           # 0=Dom .. 6=Sáb (para weekly)
    hour: int = 9              # hora UTC

@api_router.get("/agents/schedules")
async def list_schedules(user: dict = Depends(get_current_user)):
    return await db.agent_schedules.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)

@api_router.post("/agents/schedules")
async def create_schedule(req: AgentScheduleCreate, user: dict = Depends(get_current_user)):
    if req.agent_key not in AGENTS:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    client = await db.clients.find_one({"id": req.client_id, "user_id": user["user_id"]}, {"_id": 0})
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    doc = {
        "id": f"sch_{uuid.uuid4().hex[:12]}", "user_id": user["user_id"], "agent_key": req.agent_key,
        "agent_label": AGENTS[req.agent_key]["label"], "client_id": req.client_id, "client_name": client["name"],
        "model": req.model, "instructions": req.instructions, "quantity": req.quantity,
        "frequency": req.frequency, "weekday": int(req.weekday), "hour": int(req.hour),
        "active": True, "last_run_key": None, "last_run_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.agent_schedules.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.patch("/agents/schedules/{sid}")
async def toggle_schedule(sid: str, body: dict, user: dict = Depends(get_current_user)):
    r = await db.agent_schedules.update_one({"id": sid, "user_id": user["user_id"]}, {"$set": {"active": bool(body.get("active"))}})
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    return await db.agent_schedules.find_one({"id": sid}, {"_id": 0})

@api_router.delete("/agents/schedules/{sid}")
async def delete_schedule(sid: str, user: dict = Depends(get_current_user)):
    r = await db.agent_schedules.delete_one({"id": sid, "user_id": user["user_id"]})
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")
    return {"message": "Agendamento removido"}

async def _run_due_schedules():
    now = datetime.now(timezone.utc)
    our_wd = (now.weekday() + 1) % 7  # python Mon=0..Sun=6 -> nosso 0=Dom..6=Sáb
    key = f"{now.date().isoformat()}-{now.hour}"
    schedules = await db.agent_schedules.find({"active": True}).to_list(1000)
    for s in schedules:
        if int(s.get("hour", 9)) != now.hour:
            continue
        if s.get("frequency") == "weekly" and int(s.get("weekday", 1)) != our_wd:
            continue
        if s.get("last_run_key") == key:
            continue
        await db.agent_schedules.update_one({"id": s["id"]}, {"$set": {"last_run_key": key, "last_run_at": now.isoformat()}})
        try:
            client = await db.clients.find_one({"id": s["client_id"], "user_id": s["user_id"]}, {"_id": 0})
            if not client:
                continue
            req = AgentRunRequest(client_id=s["client_id"], model=s.get("model", "claude-sonnet-4-6"),
                                  instructions=s.get("instructions", ""), quantity=s.get("quantity", 5))
            gen = await _agent_generate(s["agent_key"], {"user_id": s["user_id"]}, client, req)
            await db.agent_proposals.insert_one({
                "id": f"prop_{uuid.uuid4().hex[:12]}", "user_id": s["user_id"], "agent_key": s["agent_key"],
                "agent_label": AGENTS[s["agent_key"]]["label"], "client_id": s["client_id"], "client_name": client["name"],
                "model": s.get("model", "claude-sonnet-4-6"), "status": "pendente", "title": gen["title"],
                "summary": gen["summary"], "preview": gen["preview"], "payload": gen["payload"], "result": None,
                "scheduled": True, "created_at": datetime.now(timezone.utc).isoformat(), "decided_at": None,
            })
            await log_activity(s["user_id"], "agente", f"Agente agendado {AGENTS[s['agent_key']]['label']} gerou proposta para {client['name']}")
        except Exception as e:
            logger.error(f"Falha ao rodar agendamento {s.get('id')}: {e}")

@api_router.post("/cron/agents-run")
async def cron_agents_run(request: Request, authorization: Optional[str] = Header(None)):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    token = (authorization or "").split("Bearer ", 1)[-1].strip()
    secret = os.environ.get("WEBHOOK_CRON_SECRET")
    if not secret or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=401, detail="Unauthorized")
    asyncio.create_task(_run_due_schedules())
    return {"ok": True}

@api_router.get("/integrations/nekt/status")
async def nekt_status(admin: dict = Depends(get_admin_user)):
    return {"configured": nekt.is_configured(), "url_set": bool(nekt.NEKT_URL), "token_set": bool(nekt.NEKT_TOKEN)}

@api_router.post("/integrations/nekt/test")
async def nekt_test(admin: dict = Depends(get_admin_user)):
    try:
        tools = await nekt.list_tools()
        names = [t.get("name") for t in tools if isinstance(t, dict)]
        return {"ok": True, "tools": names}
    except nekt.NektError as e:
        raise HTTPException(status_code=400, detail=str(e))

@api_router.post("/integrations/nekt/sync-clients")
async def nekt_sync_clients(admin: dict = Depends(get_admin_user)):
    sql = (
        "SELECT customer_id, nome_fantasia AS client_name, cnpj AS client_cnpj, "
        "grupo_nome AS client_group_name, segmento "
        "FROM `vanguardamartech_raw.supabase_public_vw_cliente_entidade_vbot` "
        "ORDER BY nome_fantasia LIMIT 1000"
    )
    try:
        result = await nekt.call_tool("execute_sql", {"sql_query": sql})
        rows = nekt.rows_from_result(result)
    except nekt.NektError as e:
        raise HTTPException(status_code=400, detail=str(e))
    imported = 0
    for r in rows:
        name = (r.get("client_name") or "").strip()
        if not name:
            continue
        nid = str(r.get("customer_id"))
        existing = await db.clients.find_one({"user_id": admin["user_id"], "nekt_id": nid})
        base = {
            "name": name,
            "segment": (r.get("segmento") or r.get("client_group_name") or "").strip(),
            "cnpj": (r.get("client_cnpj") or "").strip(),
            "group_name": (r.get("client_group_name") or "").strip(),
            "nekt_id": nid, "source": "nekt",
        }
        if existing:
            await db.clients.update_one({"id": existing["id"]}, {"$set": base})
        else:
            base.update({"id": f"cli_{uuid.uuid4().hex[:12]}", "user_id": admin["user_id"],
                         "brand_color": "#FF2D40", "notes": "",
                         "created_at": datetime.now(timezone.utc).isoformat()})
            await db.clients.insert_one(base)
        imported += 1
    await log_activity(admin["user_id"], "integracao", f"Sincronização Nekt: {imported} clientes")
    return {"ok": True, "imported": imported}

@api_router.get("/admin/users")
async def admin_users(user: dict = Depends(get_admin_user)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(200)
    return users

@api_router.post("/admin/users")
async def admin_create_user(req: AdminUserCreate, admin: dict = Depends(get_admin_user)):
    email = req.email.lower()
    if req.role not in ("admin", "member"):
        raise HTTPException(status_code=400, detail="Papel inválido")
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id": user_id, "email": email, "name": req.name,
        "password_hash": hash_password(req.password), "role": req.role,
        "picture": None, "plan": req.plan, "token_version": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.insert_one(doc)
    await db.app_settings.insert_one({
        "user_id": user_id, "default_model": "gpt-5.4-mini",
        "default_tone": "profissional", "agency_name": "", "meta_connected": False,
    })
    await log_activity(admin["user_id"], "usuario", f"Usuário criado: {email} ({req.role})")
    return public_user(doc)

@api_router.put("/admin/users/{user_id}")
async def admin_update_user(user_id: str, req: AdminUserUpdate, admin: dict = Depends(get_admin_user)):
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    updates = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.plan is not None:
        updates["plan"] = req.plan
    if req.role is not None:
        if req.role not in ("admin", "member"):
            raise HTTPException(status_code=400, detail="Papel inválido")
        if target["role"] == "admin" and req.role != "admin":
            admin_count = await db.users.count_documents({"role": "admin"})
            if admin_count <= 1:
                raise HTTPException(status_code=400, detail="Não é possível rebaixar o último administrador")
        updates["role"] = req.role
    if req.password:
        if len(req.password) < 6:
            raise HTTPException(status_code=400, detail="A senha deve ter ao menos 6 caracteres")
        updates["password_hash"] = hash_password(req.password)
        updates["token_version"] = target.get("token_version", 0) + 1
    if updates:
        await db.users.update_one({"user_id": user_id}, {"$set": updates})
        await log_activity(admin["user_id"], "usuario", f"Usuário atualizado: {target['email']}")
    return public_user(await db.users.find_one({"user_id": user_id}, {"_id": 0}))

@api_router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, admin: dict = Depends(get_admin_user)):
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user_id == admin["user_id"]:
        raise HTTPException(status_code=400, detail="Você não pode remover a própria conta")
    if target["role"] == "admin":
        admin_count = await db.users.count_documents({"role": "admin"})
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Não é possível remover o último administrador")
    await db.users.delete_one({"user_id": user_id})
    await db.app_settings.delete_many({"user_id": user_id})
    await log_activity(admin["user_id"], "usuario", f"Usuário removido: {target['email']}")
    return {"message": "Usuário removido"}

# ---------------- Seeding ----------------

async def seed_admin():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id, "email": admin_email, "name": "Jussara Cavalcante",
            "password_hash": hash_password(admin_password), "role": "admin", "plan": "agency",
            "picture": None, "token_version": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        await db.app_settings.insert_one({
            "user_id": user_id, "default_model": "claude-sonnet-4-6",
            "default_tone": "persuasivo", "agency_name": "Vanguarda Digital", "meta_connected": True,
        })
    elif not existing.get("role") == "admin":
        # Garante o papel de admin sem sobrescrever a senha existente (evita reset em cada boot).
        await db.users.update_one({"email": admin_email}, {"$set": {"role": "admin"}})

async def seed_demo_data():
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@example.com").lower()
    admin = await db.users.find_one({"email": admin_email}, {"_id": 0})
    if not admin:
        return
    uid = admin["user_id"]
    if await db.clients.count_documents({"user_id": uid}) > 0:
        return
    demo_clients = [
        {"id": f"cli_{uuid.uuid4().hex[:12]}", "user_id": uid, "name": "Café Aroma", "segment": "Cafeteria & Alimentação",
         "contact_name": "Marina Lopes", "contact_email": "marina@cafearoma.com.br", "brand_color": "#D97706",
         "notes": "Tom acolhedor e artesanal. Foco em cafés especiais e experiência na loja.", "status": "ativo",
         "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": f"cli_{uuid.uuid4().hex[:12]}", "user_id": uid, "name": "FitPro Academia", "segment": "Fitness & Saúde",
         "contact_name": "Rafael Souza", "contact_email": "rafael@fitpro.com.br", "brand_color": "#10B981",
         "notes": "Público 20-35 anos. Linguagem motivacional e direta. Promover planos trimestrais.", "status": "ativo",
         "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": f"cli_{uuid.uuid4().hex[:12]}", "user_id": uid, "name": "Lumière Joias", "segment": "Moda & Luxo",
         "contact_name": "Beatriz Camargo", "contact_email": "bia@lumierejoias.com.br", "brand_color": "#818CF8",
         "notes": "Marca premium. Estética minimalista, copy sofisticada, sem gírias.", "status": "ativo",
         "created_at": datetime.now(timezone.utc).isoformat()},
    ]
    await db.clients.insert_many(demo_clients)
    campaigns = []
    for c in demo_clients:
        for name, objective in [("Conversões — Tráfego Pago", "Conversões"), ("Remarketing Q2", "Remarketing")]:
            cid = f"cmp_{uuid.uuid4().hex[:12]}"
            campaigns.append({
                "id": cid, "user_id": uid, "client_id": c["id"], "client_name": c["name"],
                "name": f"{name} — {c['name']}", "objective": objective, "platform": "meta",
                "budget_daily": round(random.uniform(80, 250), 2),
                "status": random.choice(["ativa", "ativa", "pausada", "em_analise"]),
                "ad_account_id": f"act_{random.randint(10**9, 10**10 - 1)}",
                "metrics": campaign_metrics_series(cid),
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    await db.campaigns.insert_many(campaigns)
    bible = [
        {"id": f"doc_{uuid.uuid4().hex[:12]}", "user_id": uid, "title": "Guia de Tom de Voz — Café Aroma",
         "category": "Brand Persona", "content": "A voz do Café Aroma é acolhedora, artesanal e sensorial. Use palavras que evocam aroma, textura e ritual matinal. Evite jargões corporativos. Sempre mencione a origem dos grãos (Cerrado Mineiro) quando falar de produto. CTA preferido: 'Venha viver essa experiência'.",
         "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": f"doc_{uuid.uuid4().hex[:12]}", "user_id": uid, "title": "Manual de Boas Práticas — Meta Ads 2026",
         "category": "Guidelines", "content": "Estruture campanhas em 3 níveis: reconhecimento, consideração e conversão. Orçamento mínimo recomendado: R$50/dia por conjunto. Testes A/B semanais de criativo. Frequência ideal: 2-4 por semana. CTR saudável: acima de 1,5%. ROAS mínimo aceitável para e-commerce: 3.0.",
         "created_at": datetime.now(timezone.utc).isoformat()},
        {"id": f"doc_{uuid.uuid4().hex[:12]}", "user_id": uid, "title": "Playbook de Copy — FitPro Academia",
         "category": "Playbook", "content": "Copy motivacional com foco em transformação. Estrutura: dor (falta de energia, autoestima), virada (método FitPro), prova (resultados de alunos), CTA (aula experimental gratuita). Hashtags oficiais: #TreinoFitPro #SuaMelhorVersao. Nunca prometer resultados em prazos específicos.",
         "created_at": datetime.now(timezone.utc).isoformat()},
    ]
    await db.bible_documents.insert_many(bible)
    await db.alert_rules.insert_one({
        "id": f"rule_{uuid.uuid4().hex[:12]}", "user_id": uid, "name": "CTR abaixo do saudável",
        "metric": "ctr", "operator": "lt", "threshold": 1.2, "active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    logs = [
        {"kind": "geracao", "message": "Peça gerada com Claude Sonnet 4.6 (Post de Instagram)"},
        {"kind": "meta", "message": "Sincronização Meta Ads concluída: Conversões — Café Aroma"},
        {"kind": "cliente", "message": "Novo cliente cadastrado: Lumière Joias"},
        {"kind": "biblia", "message": "Documento adicionado à Bíblia: Manual de Boas Práticas — Meta Ads 2026"},
        {"kind": "alerta", "message": "Regra de alerta criada: CTR abaixo do saudável"},
    ]
    for i, l in enumerate(logs):
        await db.activity_logs.insert_one({
            "id": f"log_{uuid.uuid4().hex[:12]}", "user_id": uid, "kind": l["kind"],
            "message": l["message"], "meta": {},
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=i * 5)).isoformat(),
        })
    await evaluate_alert_rules(uid)

@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token")
    await db.password_reset_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.password_reset_tokens.create_index("token_hash", unique=True)
    await db.login_attempts.create_index("identifier")
    await db.login_attempts.create_index("email")
    await db.password_reset_requests.create_index("email")
    await db.password_reset_requests.create_index("created_at", expireAfterSeconds=900)
    await db.clients.create_index("user_id")
    await db.pieces.create_index("user_id")
    await db.campaigns.create_index("user_id")
    await db.activity_logs.create_index("user_id")
    await seed_admin()
    await seed_demo_data()

app.include_router(api_router)
app.include_router(payments_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000"), "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
