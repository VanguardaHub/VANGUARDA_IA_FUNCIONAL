from dotenv import load_dotenv
load_dotenv()

import os
import json
import uuid
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
from fastapi import FastAPI, APIRouter, Request, Response, HTTPException, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr

from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
from emergentintegrations.llm.openai.image_generation import OpenAIImageGeneration

from payments import payments_router

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

class PieceSaveRequest(BaseModel):
    client_id: Optional[str] = None
    title: str
    piece_type: str
    model: str
    prompt: str = ""
    content: str
    image: Optional[str] = None
    status: str = "rascunho"

class PieceUpdateRequest(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None

class PublishRequest(BaseModel):
    scheduled_at: Optional[str] = None

class ImageGenRequest(BaseModel):
    prompt: str

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
                "picture": gdata.get("picture"), "role": "member", "plan": "trial",
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
            "picture": data.get("picture"), "role": "member", "plan": "trial",
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
    return {
        "kpis": {
            "clients": clients_count, "pieces": pieces_count,
            "active_campaigns": len(active_campaigns), "total_campaigns": len(campaigns),
            "spend": round(total_spend, 2), "impressions": total_impressions,
            "clicks": total_clicks, "conversions": total_conversions,
            "ctr": ctr, "roas": roas, "revenue": round(revenue, 2),
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
        "Você é o motor criativo da Vanguarda.IA, uma plataforma de marketing para agências brasileiras. "
        "Escreva sempre em português do Brasil, com copy de altíssima qualidade, persuasiva e orientada a conversão. "
        "Responda APENAS com o conteúdo da peça, sem explicações ou metacomentários."
    )
    prompt = (
        f"Crie uma peça do tipo: {PIECE_TYPES[req.piece_type]}.\n"
        f"Tom de voz: {req.tone}.\n"
        f"Briefing do usuário: {req.prompt}\n"
        f"{('Contexto da marca: ' + context) if context else ''}\n\n"
        "Estrutura obrigatória da resposta:\n"
        "TÍTULO: <título curto e forte>\n"
        "LEGENDA/CORPO: <texto principal completo>\n"
        "CTA: <chamada para ação>\n"
        "HASHTAGS: <hashtags relevantes, se aplicável ao formato>"
    )

    async def event_stream():
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"piece-{uuid.uuid4().hex[:8]}",
                system_message=system,
            ).with_model(model_cfg["provider"], model_cfg["model"])
            async for ev in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(ev, TextDelta):
                    yield f"data: {json.dumps({'delta': ev.content})}\n\n"
                elif isinstance(ev, StreamDone):
                    break
            await log_activity(user["user_id"], "geracao", f"Peça gerada com {model_cfg['label']} ({PIECE_TYPES[req.piece_type]})")
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logger.error(f"Erro na geração: {e}")
            yield f"data: {json.dumps({'error': 'Falha na geração com IA. Tente novamente.'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@api_router.post("/pieces/generate-image")
async def generate_image(req: ImageGenRequest, user: dict = Depends(get_current_user)):
    try:
        gen = OpenAIImageGeneration(api_key=EMERGENT_LLM_KEY)
        images = await gen.generate_images(
            prompt=f"Criativo publicitário profissional para rede social, alta qualidade visual: {req.prompt}",
            model="gpt-image-1", number_of_images=1, quality="medium",
        )
        b64 = base64.b64encode(images[0]).decode()
        await log_activity(user["user_id"], "geracao", "Imagem gerada com IA (GPT Image 1)")
        return {"image": f"data:image/png;base64,{b64}"}
    except Exception as e:
        logger.error(f"Erro ao gerar imagem: {e}")
        raise HTTPException(status_code=500, detail="Falha ao gerar imagem com IA")

@api_router.get("/pieces")
async def list_pieces(user: dict = Depends(get_current_user)):
    return await db.pieces.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)

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
    return s

@api_router.put("/settings")
async def update_settings(req: SettingsUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "default_model" in updates and updates["default_model"] not in AI_MODELS:
        raise HTTPException(status_code=400, detail="Modelo inválido")
    await db.app_settings.update_one({"user_id": user["user_id"]}, {"$set": updates}, upsert=True)
    await log_activity(user["user_id"], "config", "Configurações atualizadas")
    return await db.app_settings.find_one({"user_id": user["user_id"]}, {"_id": 0})

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
