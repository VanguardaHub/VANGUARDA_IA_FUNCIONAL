import { useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

export default function AuthCallback() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;
    const hash = window.location.hash;
    const sessionId = new URLSearchParams(hash.replace("#", "")).get("session_id");
    const exchange = async () => {
      try {
        const { data } = await api.post("/auth/google/session", { session_id: sessionId });
        setUser(data);
        window.history.replaceState(null, "", window.location.pathname);
        navigate("/dashboard", { replace: true, state: { user: data } });
      } catch {
        navigate("/login", { replace: true });
      }
    };
    exchange();
  }, [navigate, setUser]);

  return (
    <div className="min-h-screen bg-[#0B0B0D] flex flex-col items-center justify-center gap-4" data-testid="auth-callback">
      <div className="w-10 h-10 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
      <p className="text-slate-400 text-sm">Autenticando com Google...</p>
    </div>
  );
}
