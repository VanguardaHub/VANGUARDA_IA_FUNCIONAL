import { useEffect, useState, useRef } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { API } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function PaymentResult() {
  const { status } = useParams();
  const [params] = useSearchParams();
  const { checkAuth } = useAuth();
  const sessionId = params.get("session_id");
  const [state, setState] = useState("checking");
  const attempts = useRef(0);

  useEffect(() => {
    if (status !== "success" || !sessionId) {
      setState(status === "cancel" ? "cancelled" : "failed");
      return;
    }
    const poll = async () => {
      try {
        const resp = await fetch(`${API}/payments/status/${sessionId}`);
        const data = await resp.json();
        if (data.payment_status === "paid") {
          setState("paid");
          checkAuth();
          return;
        }
      } catch {}
      attempts.current += 1;
      if (attempts.current < 10) {
        setTimeout(poll, 2000);
      } else {
        setState("pending");
      }
    };
    poll();
  }, [status, sessionId, checkAuth]);

  return (
    <div className="min-h-screen bg-[#0B0B0D] flex items-center justify-center p-6" data-testid="payment-result-page">
      <div className="glass-card p-10 max-w-md w-full text-center">
        {(state === "checking") && (
          <>
            <Loader2 className="w-12 h-12 text-red-400 animate-spin mx-auto mb-4" />
            <h1 className="font-display font-bold text-2xl mb-2">Confirmando pagamento...</h1>
            <p className="text-sm text-slate-400">Aguarde enquanto validamos sua assinatura.</p>
          </>
        )}
        {state === "paid" && (
          <>
            <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-4" />
            <h1 className="font-display font-bold text-2xl mb-2" data-testid="payment-success-title">Assinatura ativada!</h1>
            <p className="text-sm text-slate-400 mb-6">Seu plano foi atualizado. Aproveite todos os recursos da Vanguarda.IA.</p>
            <Link to="/dashboard">
              <Button className="bg-red-600 hover:bg-red-500 text-white rounded-full px-8" data-testid="go-dashboard-button">
                Ir para o dashboard
              </Button>
            </Link>
          </>
        )}
        {state === "pending" && (
          <>
            <Loader2 className="w-12 h-12 text-amber-400 mx-auto mb-4" />
            <h1 className="font-display font-bold text-2xl mb-2">Pagamento em processamento</h1>
            <p className="text-sm text-slate-400 mb-6">A confirmação pode levar alguns instantes. Verifique seus planos em breve.</p>
            <Link to="/planos">
              <Button variant="outline" className="border-slate-700 text-slate-200 rounded-full px-8" data-testid="go-plans-button">
                Voltar aos planos
              </Button>
            </Link>
          </>
        )}
        {(state === "cancelled" || state === "failed") && (
          <>
            <XCircle className="w-12 h-12 text-rose-400 mx-auto mb-4" />
            <h1 className="font-display font-bold text-2xl mb-2" data-testid="payment-cancel-title">Pagamento não concluído</h1>
            <p className="text-sm text-slate-400 mb-6">Nenhuma cobrança foi feita. Você pode tentar novamente quando quiser.</p>
            <Link to="/planos">
              <Button className="bg-red-600 hover:bg-red-500 text-white rounded-full px-8" data-testid="retry-plans-button">
                Ver planos
              </Button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
