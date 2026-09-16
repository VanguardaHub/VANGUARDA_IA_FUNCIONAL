import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Zap } from "lucide-react";
import { toast } from "sonner";

export function GoogleButton({ testid }) {
  const handleGoogle = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };
  return (
    <Button type="button" variant="outline" onClick={handleGoogle}
      className="w-full border-slate-700 bg-white/5 hover:bg-white/10 text-slate-200 h-11"
      data-testid={testid}>
      <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.1a7.06 7.06 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/></svg>
      Continuar com Google
    </Button>
  );
}

export function AuthShell({ children, title, subtitle }) {
  return (
    <div className="min-h-screen bg-[#0B0B0D] noise-overlay flex items-center justify-center p-6">
      <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[500px] h-[300px] bg-red-600/15 blur-[120px] rounded-full pointer-events-none" />
      <div className="w-full max-w-md relative">
        <div className="flex items-center justify-center gap-2 mb-8">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <span className="font-display font-extrabold text-xl tracking-tight">Vanguarda<span className="text-red-400">.IA</span></span>
        </div>
        <div className="glass-card p-8">
          <h1 className="font-display font-bold text-2xl tracking-tight mb-1">{title}</h1>
          <p className="text-sm text-slate-400 mb-6">{subtitle}</p>
          {children}
        </div>
      </div>
    </div>
  );
}

export default function Login() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/login", form);
      setUser(data);
      toast.success(`Bem-vinda de volta, ${data.name.split(" ")[0]}!`);
      navigate("/dashboard");
    } catch (err) {
      setError(formatApiError(err, "Falha ao entrar"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="Entrar na plataforma" subtitle="Acesse o cockpit da sua agência">
      <form onSubmit={submit} className="space-y-4" data-testid="login-form">
        {error && <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm" data-testid="login-error">{error}</div>}
        <div className="space-y-2">
          <Label htmlFor="email" className="text-slate-300">E-mail</Label>
          <Input id="email" type="email" required value={form.email} data-testid="login-email-input"
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="bg-[#0E0E11] border-slate-700 h-11" placeholder="voce@agencia.com.br" />
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password" className="text-slate-300">Senha</Label>
            <Link to="/forgot-password" className="text-xs text-red-400 hover:text-red-300" data-testid="forgot-password-link">Esqueci a senha</Link>
          </div>
          <Input id="password" type="password" required value={form.password} data-testid="login-password-input"
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="bg-[#0E0E11] border-slate-700 h-11" placeholder="••••••••" />
        </div>
        <Button type="submit" disabled={loading} className="w-full bg-red-600 hover:bg-red-500 text-white h-11" data-testid="login-submit-button">
          {loading ? "Entrando..." : "Entrar"}
        </Button>
      </form>
      <div className="flex items-center gap-3 my-5">
        <div className="flex-1 h-px bg-slate-800" />
        <span className="text-xs text-slate-500">ou</span>
        <div className="flex-1 h-px bg-slate-800" />
      </div>
      <GoogleButton testid="google-login-button" />
      <p className="text-sm text-slate-400 text-center mt-6">
        Não tem conta?{" "}
        <Link to="/register" className="text-red-400 hover:text-red-300 font-medium" data-testid="go-to-register-link">Criar conta</Link>
      </p>
    </AuthShell>
  );
}
