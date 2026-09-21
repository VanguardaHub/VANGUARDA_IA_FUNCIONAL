"""Backend tests for AI cost tracking, pricing settings, pieces cost binding, dashboard KPIs, cost report."""
import os
import json
import uuid
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "jussaracavalcante25@gmail.com"
ADMIN_PASSWORD = "Vanguarda@2026"


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    # cookies now on session
    assert s.cookies.get("access_token") or s.cookies.get("session_token"), f"no auth cookie: {s.cookies.get_dict()}"
    return s


@pytest.fixture(scope="module")
def headers(session):
    # kept for backward compatibility with call sites
    return session


# --- Pricing settings ---
def test_get_settings_pricing_defaults(headers):
    r = headers.get(f"{API}/settings", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert "pricing" in data
    p = data["pricing"]
    for k in ("usd_to_brl", "markup_pct", "image_high_per_unit", "models"):
        assert k in p, f"missing {k} in pricing"
    assert "gpt-5.4-mini" in p["models"]
    assert "claude-sonnet-4-6" in p["models"]


def test_put_settings_pricing_persists(headers):
    # capture original markup
    orig = headers.get(f"{API}/settings", timeout=15).json()["pricing"]["markup_pct"]
    try:
        r = headers.put(f"{API}/settings", json={"pricing": {"markup_pct": 150}}, timeout=15)
        assert r.status_code == 200
        r2 = headers.get(f"{API}/settings", timeout=15)
        assert r2.json()["pricing"]["markup_pct"] == 150.0
    finally:
        headers.put(f"{API}/settings", json={"pricing": {"markup_pct": orig}}, timeout=15)


# --- SSE generate: stage=copy first, refacao_texto second ---
def _stream_generate(headers, gen_group_id, prompt="Fale sobre café especial em 2 linhas"):
    body = {
        "piece_type": "post_instagram",
        "model": "gpt-5.4-mini",
        "tone": "profissional",
        "prompt": prompt,
        "gen_group_id": gen_group_id,
    }
    with headers.post(f"{API}/pieces/generate", json=body, stream=True, timeout=120) as r:
        assert r.status_code == 200, r.text
        final = None
        content = ""
        for raw in r.iter_lines(decode_unicode=True):
            if not raw or not raw.startswith("data:"):
                continue
            evt = json.loads(raw[5:].strip())
            if "delta" in evt:
                content += evt["delta"]
            if evt.get("done"):
                final = evt
                break
        assert final is not None, "no final SSE event"
        return final, content


@pytest.fixture(scope="module")
def gen_group_and_final(headers):
    ggid = f"gg_{uuid.uuid4().hex[:12]}"
    final1, content1 = _stream_generate(headers, ggid)
    final2, content2 = _stream_generate(headers, ggid)
    return {"ggid": ggid, "final1": final1, "final2": final2, "content1": content1, "content2": content2}


def test_generate_first_stage_copy(gen_group_and_final):
    f = gen_group_and_final["final1"]
    assert f.get("done") is True
    assert f.get("stage") == "copy"
    assert isinstance(f.get("cost_brl"), (int, float))
    assert f["cost_brl"] > 0
    assert isinstance(f.get("tokens"), int)


def test_generate_second_stage_refacao_texto(gen_group_and_final):
    f = gen_group_and_final["final2"]
    assert f.get("done") is True
    assert f.get("stage") == "refacao_texto", f"expected refacao_texto, got {f.get('stage')}"
    assert f["cost_brl"] > 0


# --- Save piece binds cost ---
@pytest.fixture(scope="module")
def saved_piece(headers, gen_group_and_final):
    ggid = gen_group_and_final["ggid"]
    content = gen_group_and_final["content2"] or "Teste"
    body = {
        "title": f"TEST_piece_{uuid.uuid4().hex[:6]}",
        "piece_type": "post_instagram",
        "model": "gpt-5.4-mini",
        "prompt": "prompt teste",
        "content": content,
        "status": "rascunho",
        "gen_group_id": ggid,
    }
    r = headers.post(f"{API}/pieces", json=body, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


def test_save_piece_returns_cost_fields(saved_piece):
    p = saved_piece
    assert p.get("cost_brl", 0) > 0
    assert p.get("regen_count") == 1  # one refacao_texto
    assert isinstance(p.get("cost_breakdown"), list)
    assert len(p["cost_breakdown"]) >= 2
    stages = {b["stage"] for b in p["cost_breakdown"]}
    assert "copy" in stages
    assert "refacao_texto" in stages
    assert p.get("billable_brl") is not None
    # billable = cost * (1+markup/100). Default 100 => 2x. Verify roughly.
    assert p["billable_brl"] >= p["cost_brl"] * 0.99


def test_list_pieces_has_billable(headers, saved_piece):
    r = headers.get(f"{API}/pieces", timeout=15)
    assert r.status_code == 200
    lst = r.json()
    found = next((x for x in lst if x["id"] == saved_piece["id"]), None)
    assert found is not None
    assert found.get("cost_brl", 0) > 0
    assert found.get("billable_brl") is not None


def test_dashboard_kpis_ai(headers):
    r = headers.get(f"{API}/dashboard", timeout=15)
    assert r.status_code == 200
    d = r.json()
    kpis = d.get("kpis") or d
    assert "ai_cost_brl" in kpis
    assert "ai_billable_brl" in kpis
    assert isinstance(kpis["ai_cost_brl"], (int, float))
    assert isinstance(kpis["ai_billable_brl"], (int, float))


def test_reports_costs(headers):
    r = headers.get(f"{API}/reports/costs", timeout=15)
    assert r.status_code == 200
    d = r.json()
    for k in ("rows", "total_cost_brl", "total_billable_brl", "markup_pct"):
        assert k in d
    assert isinstance(d["rows"], list)
    # markup relation
    assert d["total_billable_brl"] >= d["total_cost_brl"] * 0.99


# --- Cleanup ---
def test_cleanup_pieces(headers, saved_piece):
    r = headers.delete(f"{API}/pieces/{saved_piece['id']}", timeout=15)
    assert r.status_code in (200, 204, 404)
