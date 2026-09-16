import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { AuthShell, GoogleButton } from "./Login";

export default function Register() {
  const navigate = useNavigate();
  const { setUser } = useAuth();
  const [form, setForm] = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { data } = await api.post("/auth/register", form);
      setUser(data);
      toast.success("Conta criada! Bem-vinda à Vanguarda.IA");
      navigate("/dashboard");
    } catch (err) {
      setError(formatApiError(err, "Falha ao criar conta"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="Criar sua conta" subtitle="Comece grátis — sem cartão de crédito">
      <form onSubmit={submit} className="space-y-4" data-testid="register-form">
        {error && <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm" data-testid="register-error">{error}</div>}
        <div className="space-y-2">
          <Label htmlFor="name" className="text-slate-300">Nome completo</Label>
          <Input id="name" required value={form.name} data-testid="register-name-input"
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="bg-[#0E0E11] border-slate-700 h-11" placeholder="Maria Silva" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email" className="text-slate-300">E-mail</Label>
          <Input id="email" type="email" required value={form.email} data-testid="register-email-input"
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="bg-[#0E0E11] border-slate-700 h-11" placeholder="voce@agencia.com.br" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password" className="text-slate-300">Senha</Label>
          <Input id="password" type="password" required minLength={6} value={form.password} data-testid="register-password-input"
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="bg-[#0E0E11] border-slate-700 h-11" placeholder="Mínimo 6 caracteres" />
        </div>
        <Button type="submit" disabled={loading} className="w-full bg-red-600 hover:bg-red-500 text-white h-11" data-testid="register-submit-button">
          {loading ? "Criando..." : "Criar conta grátis"}
        </Button>
      </form>
      <div className="flex items-center gap-3 my-5">
        <div className="flex-1 h-px bg-slate-800" />
        <span className="text-xs text-slate-500">ou</span>
        <div className="flex-1 h-px bg-slate-800" />
      </div>
      <GoogleButton testid="google-register-button" />
      <p className="text-sm text-slate-400 text-center mt-6">
        Já tem conta?{" "}
        <Link to="/login" className="text-red-400 hover:text-red-300 font-medium" data-testid="go-to-login-link">Entrar</Link>
      </p>
    </AuthShell>
  );
}
