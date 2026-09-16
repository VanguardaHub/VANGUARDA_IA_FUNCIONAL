import { useState } from "react";
import { Link } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AuthShell } from "./Login";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/auth/forgot-password", { email });
    } catch {}
    setSent(true);
    setLoading(false);
  };

  return (
    <AuthShell title="Redefinir senha" subtitle="Enviaremos um link de redefinição para seu e-mail">
      {sent ? (
        <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm" data-testid="forgot-success">
          Se o e-mail estiver cadastrado, enviamos um link de redefinição. Verifique sua caixa de entrada.
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" data-testid="forgot-form">
          <div className="space-y-2">
            <Label htmlFor="email" className="text-slate-300">E-mail</Label>
            <Input id="email" type="email" required value={email} data-testid="forgot-email-input"
              onChange={(e) => setEmail(e.target.value)}
              className="bg-[#0E0E11] border-slate-700 h-11" placeholder="voce@agencia.com.br" />
          </div>
          <Button type="submit" disabled={loading} className="w-full bg-red-600 hover:bg-red-500 text-white h-11" data-testid="forgot-submit-button">
            {loading ? "Enviando..." : "Enviar link de redefinição"}
          </Button>
        </form>
      )}
      <p className="text-sm text-slate-400 text-center mt-6">
        <Link to="/login" className="text-red-400 hover:text-red-300 font-medium" data-testid="back-to-login-link">Voltar para o login</Link>
      </p>
    </AuthShell>
  );
}
