"""Cliente MCP do Nekt (JSON-RPC 2.0 sobre HTTP Streamable) para usar como banco de clientes."""
import os
import json
import httpx

NEKT_URL = os.environ.get("NEKT_MCP_URL", "").strip()
NEKT_TOKEN = os.environ.get("NEKT_MCP_TOKEN", "").strip()
PROTOCOL_VERSION = "2026-07-28"


class NektError(Exception):
    pass


def is_configured() -> bool:
    return bool(NEKT_URL and NEKT_TOKEN)


def _headers(session_id: str | None = None) -> dict:
    h = {
        "Authorization": f"Bearer {NEKT_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session_id:
        h["Mcp-Session-Id"] = session_id
    return h


def _parse(resp: httpx.Response, rpc_id: int) -> dict:
    ctype = resp.headers.get("content-type", "")
    if "text/event-stream" in ctype:
        found = {}
        for line in resp.text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                try:
                    obj = json.loads(line[5:].strip())
                    if obj.get("id") == rpc_id or "result" in obj or "error" in obj:
                        found = obj
                except Exception:
                    continue
        data = found
    else:
        data = resp.json()
    if data.get("error"):
        raise NektError(str(data["error"]))
    return data.get("result", {})


async def _rpc(client: httpx.AsyncClient, session_id, method, params, rpc_id):
    payload = {"jsonrpc": "2.0", "id": rpc_id, "method": method}
    if params is not None:
        payload["params"] = params
    resp = await client.post(NEKT_URL, json=payload, headers=_headers(session_id), timeout=90)
    if resp.status_code >= 400:
        raise NektError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    sid = resp.headers.get("Mcp-Session-Id", session_id)
    return _parse(resp, rpc_id), sid


async def _open_session(client: httpx.AsyncClient):
    result, sid = await _rpc(client, None, "initialize", {
        "protocolVersion": PROTOCOL_VERSION,
        "capabilities": {},
        "clientInfo": {"name": "Vanguarda.IA", "version": "1.0"},
    }, rpc_id=1)
    try:
        await client.post(NEKT_URL, json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                          headers=_headers(sid), timeout=30)
    except Exception:
        pass
    return sid, result


async def list_tools() -> list:
    if not is_configured():
        raise NektError("Integração Nekt não configurada (defina NEKT_MCP_URL e NEKT_MCP_TOKEN).")
    async with httpx.AsyncClient() as client:
        sid, _ = await _open_session(client)
        result, _ = await _rpc(client, sid, "tools/list", {}, rpc_id=2)
        return result.get("tools", result if isinstance(result, list) else [])


async def call_tool(name: str, arguments: dict):
    if not is_configured():
        raise NektError("Integração Nekt não configurada (defina NEKT_MCP_URL e NEKT_MCP_TOKEN).")
    async with httpx.AsyncClient() as client:
        sid, _ = await _open_session(client)
        result, _ = await _rpc(client, sid, "tools/call", {"name": name, "arguments": arguments}, rpc_id=2)
        return result


def extract_text(tool_result: dict) -> str:
    """Extrai o texto do content[] retornado por tools/call."""
    if not isinstance(tool_result, dict):
        return str(tool_result)
    parts = []
    for item in tool_result.get("content", []) or []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(item.get("text", ""))
    return "\n".join(parts)


def rows_from_result(tool_result: dict) -> list:
    """Extrai linhas (lista de dicts) do resultado de execute_sql (formato columns/data) ou JSON."""
    text = extract_text(tool_result)
    try:
        data = json.loads(text)
    except Exception:
        return []
    if isinstance(data, dict) and isinstance(data.get("columns"), list) and isinstance(data.get("data"), list):
        cols = [c.get("name") if isinstance(c, dict) else c for c in data["columns"]]
        return [dict(zip(cols, row)) for row in data["data"]]
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        for key in ("rows", "results"):
            if isinstance(data.get(key), list):
                return [r for r in data[key] if isinstance(r, dict)]
    return []
