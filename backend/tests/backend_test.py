"""Backend regression tests for Vanguarda.IA"""
import os
import uuid
import pytest
import requests

from pathlib import Path

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: frontend/.env resolvido em relacao ao repositorio, nao a um
    # caminho absoluto de container.
    env_file = Path(__file__).resolve().parents[2] / "frontend" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
if not BASE_URL:
    BASE_URL = "http://127.0.0.1:8001"

API = f"{BASE_URL}/api"

# Credenciais lidas do ambiente — as mesmas que o backend usa para semear o
# admin. Nunca fixe senha em codigo versionado.
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
if not ADMIN_EMAIL or not ADMIN_PASSWORD:
    pytest.skip(
        "Defina ADMIN_EMAIL e ADMIN_PASSWORD (os mesmos do backend) para rodar a suite.",
        allow_module_level=True,
    )


# ---------------- Fixtures ----------------

@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return s


@pytest.fixture(scope="session")
def new_user_session():
    """Create a fresh user for register/reset tests."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = s.post(f"{API}/auth/register", json={"name": "Test User", "email": email, "password": "secret123"})
    assert r.status_code == 200, f"Register failed: {r.status_code} {r.text}"
    s.email = email
    return s


# ---------------- Auth tests ----------------

class TestAuth:
    def test_login_success(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == ADMIN_EMAIL
        assert data["role"] == "admin"
        assert "password_hash" not in data

    def test_login_wrong_password(self):
        r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": "wrongpass"})
        assert r.status_code == 401
        assert "incorret" in r.json().get("detail", "").lower() or "e-mail" in r.json().get("detail", "").lower()

    def test_register_and_me(self, new_user_session):
        r = new_user_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json()["plan"] == "trial"

    def test_forgot_password_generic_response(self):
        r1 = requests.post(f"{API}/auth/forgot-password", json={"email": "nonexistent@example.com"})
        r2 = requests.post(f"{API}/auth/forgot-password", json={"email": ADMIN_EMAIL})
        assert r1.status_code == 200
        assert r2.status_code == 200
        # Identical generic response
        assert r1.json() == r2.json()

    def test_refresh_endpoint(self, admin_session):
        r = admin_session.post(f"{API}/auth/refresh")
        assert r.status_code == 200

    def test_unauth_access_blocked(self):
        r = requests.get(f"{API}/dashboard")
        assert r.status_code == 401


# ---------------- Dashboard ----------------

class TestDashboard:
    def test_dashboard_kpis(self, admin_session):
        r = admin_session.get(f"{API}/dashboard")
        assert r.status_code == 200
        data = r.json()
        assert "kpis" in data
        kpis = data["kpis"]
        assert kpis["clients"] >= 3
        assert kpis["total_campaigns"] >= 6
        assert isinstance(kpis["roas"], (int, float))
        assert isinstance(data["series"], list)


# ---------------- Clients CRUD ----------------

class TestClients:
    def test_list_seeded(self, admin_session):
        r = admin_session.get(f"{API}/clients")
        assert r.status_code == 200
        clients = r.json()
        assert len(clients) >= 3
        names = [c["name"] for c in clients]
        assert "Café Aroma" in names

    def test_create_get_update_delete(self, admin_session):
        # Create
        payload = {"name": "TEST_Cliente", "segment": "Tech", "contact_name": "T", "contact_email": "t@x.com"}
        r = admin_session.post(f"{API}/clients", json=payload)
        assert r.status_code == 200
        cid = r.json()["id"]
        # Get
        r = admin_session.get(f"{API}/clients/{cid}")
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_Cliente"
        # Update
        r = admin_session.put(f"{API}/clients/{cid}", json={"segment": "Fintech"})
        assert r.status_code == 200
        assert r.json()["segment"] == "Fintech"
        # Delete
        r = admin_session.delete(f"{API}/clients/{cid}")
        assert r.status_code == 200
        r = admin_session.get(f"{API}/clients/{cid}")
        assert r.status_code == 404


# ---------------- Pieces ----------------

class TestPieces:
    def test_list_pieces(self, admin_session):
        r = admin_session.get(f"{API}/pieces")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_save_and_approve_piece(self, admin_session):
        r = admin_session.post(f"{API}/pieces", json={
            "title": "TEST_Peca", "piece_type": "post_instagram", "model": "gpt-5.4-mini",
            "content": "Conteúdo de teste", "status": "rascunho",
        })
        assert r.status_code == 200
        pid = r.json()["id"]
        r = admin_session.put(f"{API}/pieces/{pid}", json={"status": "aprovada"})
        assert r.status_code == 200
        assert r.json()["status"] == "aprovada"
        admin_session.delete(f"{API}/pieces/{pid}")

    def test_generate_piece_stream(self, admin_session):
        # Stream endpoint should return 200 with SSE content-type
        r = admin_session.post(f"{API}/pieces/generate", json={
            "piece_type": "post_instagram", "model": "gpt-5.4-mini", "tone": "profissional",
            "prompt": "Anuncie um café especial da região do Cerrado",
        }, stream=True, timeout=60)
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        got_delta = False
        got_error = False
        chunks_read = 0
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            chunks_read += 1
            if '"delta"' in line:
                got_delta = True
            if '"error"' in line:
                got_error = True
            if '"done"' in line or chunks_read > 300:
                break
        r.close()
        assert not got_error, "LLM stream returned error"
        assert got_delta, "No delta content received from LLM"

    def test_generate_piece_invalid_model(self, admin_session):
        r = admin_session.post(f"{API}/pieces/generate", json={
            "piece_type": "post_instagram", "model": "invalid-model", "prompt": "x",
        })
        assert r.status_code == 400


# ---------------- Bible ----------------

class TestBible:
    def test_list_docs(self, admin_session):
        r = admin_session.get(f"{API}/bible/documents")
        assert r.status_code == 200
        assert len(r.json()) >= 3

    def test_create_doc(self, admin_session):
        r = admin_session.post(f"{API}/bible/documents", json={
            "title": "TEST_Doc", "category": "Test", "content": "Conteúdo teste"
        })
        assert r.status_code == 200
        doc_id = r.json()["id"]
        admin_session.delete(f"{API}/bible/documents/{doc_id}")

    def test_bible_ask_stream(self, admin_session):
        r = admin_session.post(f"{API}/bible/ask", json={
            "question": "Qual o tom de voz do Café Aroma?", "model": "gpt-5.4-mini"
        }, stream=True, timeout=60)
        assert r.status_code == 200
        got_sources = False
        got_delta = False
        chunks = 0
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            chunks += 1
            if '"sources"' in line:
                got_sources = True
            if '"delta"' in line:
                got_delta = True
            if '"done"' in line or chunks > 300:
                break
        r.close()
        assert got_sources
        assert got_delta


# ---------------- Campaigns ----------------

class TestCampaigns:
    def test_list(self, admin_session):
        r = admin_session.get(f"{API}/campaigns")
        assert r.status_code == 200
        campaigns = r.json()
        assert len(campaigns) >= 6
        assert "totals" in campaigns[0]
        assert "roas" in campaigns[0]["totals"]

    def test_sync_and_toggle_status(self, admin_session):
        campaigns = admin_session.get(f"{API}/campaigns").json()
        cid = campaigns[0]["id"]
        r = admin_session.post(f"{API}/campaigns/{cid}/sync")
        assert r.status_code == 200
        assert "latest" in r.json()
        r = admin_session.post(f"{API}/campaigns/{cid}/status", json={"status": "pausada"})
        assert r.status_code == 200
        assert r.json()["status"] == "pausada"
        # Restore
        admin_session.post(f"{API}/campaigns/{cid}/status", json={"status": "ativa"})

    def test_create_campaign(self, admin_session):
        clients = admin_session.get(f"{API}/clients").json()
        r = admin_session.post(f"{API}/campaigns", json={
            "client_id": clients[0]["id"], "name": "TEST_Campaign",
            "objective": "Conversões", "budget_daily": 100.0
        })
        assert r.status_code == 200


# ---------------- Logs & Alerts ----------------

class TestLogs:
    def test_list_logs(self, admin_session):
        r = admin_session.get(f"{API}/logs")
        assert r.status_code == 200
        data = r.json()
        assert "logs" in data
        assert "occurrences" in data
        assert len(data["logs"]) > 0

    def test_alert_rules(self, admin_session):
        r = admin_session.get(f"{API}/alerts/rules")
        assert r.status_code == 200
        rules = r.json()
        assert any(rule["name"] == "CTR abaixo do saudável" for rule in rules)

    def test_create_delete_rule(self, admin_session):
        r = admin_session.post(f"{API}/alerts/rules", json={
            "name": "TEST_Rule", "metric": "spend", "operator": "gt", "threshold": 1000.0
        })
        assert r.status_code == 200
        rid = r.json()["id"]
        r = admin_session.delete(f"{API}/alerts/rules/{rid}")
        assert r.status_code == 200


# ---------------- Settings ----------------

class TestSettings:
    def test_get_settings(self, admin_session):
        r = admin_session.get(f"{API}/settings")
        assert r.status_code == 200
        data = r.json()
        assert "default_model" in data
        assert "available_models" in data
        assert len(data["available_models"]) == 2

    def test_update_settings(self, admin_session):
        r = admin_session.put(f"{API}/settings", json={"default_model": "claude-sonnet-4-6"})
        assert r.status_code == 200
        assert r.json()["default_model"] == "claude-sonnet-4-6"

    def test_update_invalid_model(self, admin_session):
        r = admin_session.put(f"{API}/settings", json={"default_model": "invalid"})
        assert r.status_code == 400

    def test_admin_users(self, admin_session):
        r = admin_session.get(f"{API}/admin/users")
        assert r.status_code == 200
        users = r.json()
        assert any(u["email"] == ADMIN_EMAIL for u in users)
        for u in users:
            assert "password_hash" not in u


# ---------------- Payments ----------------

class TestPayments:
    def test_list_plans(self):
        r = requests.get(f"{API}/payments/plans")
        assert r.status_code == 200
        plans = r.json()
        # Should have at least the 6 configured plans (may fail if Stripe not configured)
        assert isinstance(plans, list)

    def test_checkout_creation(self, admin_session):
        me = admin_session.get(f"{API}/auth/me").json()
        r = admin_session.post(f"{API}/payments/checkout", json={
            "lookup_key": "starter_monthly", "origin_url": BASE_URL, "user_id": me["user_id"]
        })
        # If Stripe not configured, will 500; accept both but assert URL if success
        assert r.status_code in (200, 500)
        if r.status_code == 200:
            data = r.json()
            assert "checkout_url" in data
            assert "session_id" in data
            assert data["checkout_url"].startswith("https://")
