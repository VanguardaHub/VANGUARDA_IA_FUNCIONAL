import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

export function formatApiError(e, fallback = "Algo deu errado. Tente novamente.") {
  const detail = e?.response?.data?.detail;
  if (detail == null) return e?.message || fallback;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((x) => (x && typeof x.msg === "string" ? x.msg : JSON.stringify(x))).filter(Boolean).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export async function streamSSE(path, body, { onDelta, onMeta, onDone, onError }) {
  try {
    const resp = await fetch(`${API}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      let msg = "Erro na requisição";
      try {
        const data = await resp.json();
        msg = typeof data.detail === "string" ? data.detail : msg;
      } catch {}
      throw new Error(msg);
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop();
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        try {
          const payload = JSON.parse(line.slice(5).trim());
          if (payload.delta) onDelta?.(payload.delta);
          if (payload.sources) onMeta?.(payload);
          if (payload.error) onError?.(payload.error);
          if (payload.done) onDone?.(payload);
        } catch {}
      }
    }
  } catch (e) {
    onError?.(e.message || "Falha na conexão");
  }
}

export function formatBRL(value) {
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(value || 0);
}

export function formatBRLPrecise(value) {
  const v = Number(value) || 0;
  const digits = v !== 0 && Math.abs(v) < 0.01 ? 4 : 2;
  return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(v);
}

export function formatNumber(value) {
  return new Intl.NumberFormat("pt-BR").format(value || 0);
}
