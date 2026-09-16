import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { AuthShell } from "./Login";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") || "";
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await api.post("/auth/reset-password", { token, password });
      toast.success("Senha redefinida! Faça login com a nova senha.");
      navigate("/login");
    } catch (err) {
      setError(formatApiError(err, "Falha ao redefinir senha"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell title="Nova senha" subtitle="Escolha uma nova senha para sua conta">
      {!token ? (
        <div className="p-4 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm" data-testid="reset-invalid">
          Link inválido. Solicite um novo link de redefinição.
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4" data-testid="reset-form">
          {error && <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm" data-testid="reset-error">{error}</div>}
          <div className="space-y-2">
            <Label htmlFor="password" className="text-slate-300">Nova senha</Label>
            <Input id="password" type="password" required minLength={6} value={password} data-testid="reset-password-input"
              onChange={(e) => setPassword(e.target.value)}
              className="bg-[#0E0E11] border-slate-700 h-11" placeholder="Mínimo 6 caracteres" />
          </div>
          <Button type="submit" disabled={loading} className="w-full bg-red-600 hover:bg-red-500 text-white h-11" data-testid="reset-submit-button">
            {loading ? "Salvando..." : "Redefinir senha"}
          </Button>
        </form>
      )}
      <p className="text-sm text-slate-400 text-center mt-6">
        <Link to="/login" className="text-red-400 hover:text-red-300 font-medium" data-testid="reset-back-login-link">Voltar para o login</Link>
      </p>
    </AuthShell>
  );
}
