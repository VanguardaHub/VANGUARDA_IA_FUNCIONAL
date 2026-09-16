import { useState } from "react";
import { api, formatApiError, formatBRL } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Check, Loader2, Crown } from "lucide-react";
import { toast } from "sonner";

const PLANS = [
  {
    id: "starter", name: "Starter Agência", monthly: 97, yearly: 930,
    desc: "Para agências começando com IA",
    features: ["5 clientes ativos", "50 gerações de IA/mês", "Bíblia da marca", "Dashboard de indicadores", "1 usuário"],
  },
  {
    id: "pro", name: "Pro Scale", monthly: 197, yearly: 1890, highlight: true,
    desc: "Para agências em crescimento",
    features: ["20 clientes ativos", "Gerações de IA ilimitadas", "Imagens com IA incluídas", "Piloto Meta Ads", "Alertas inteligentes", "5 usuários"],
  },
  {
    id: "agency", name: "Enterprise White-label", monthly: 397, yearly: 3810,
    desc: "Para operações de grande escala",
    features: ["Clientes ilimitados", "White-label completo", "API dedicada", "Usuários ilimitados", "Suporte prioritário", "Onboarding dedicado"],
  },
];

const PLAN_LABELS = { trial: "Trial gratuito", starter: "Starter Agência", pro: "Pro Scale", agency: "Enterprise White-label" };

export default function Plans() {
  const { user, checkAuth } = useAuth();
  const [yearly, setYearly] = useState(false);
  const [loading, setLoading] = useState(null);

  const checkout = async (planId) => {
    const lookupKey = `${planId}_${yearly ? "yearly" : "monthly"}`;
    setLoading(lookupKey);
    try {
      const { data } = await api.post("/payments/checkout", {
        lookup_key: lookupKey,
        origin_url: window.location.origin,
        user_id: user?.user_id,
      });
      window.location.href = data.checkout_url;
    } catch (err) {
      toast.error(formatApiError(err, "Falha ao iniciar checkout"));
      setLoading(null);
    }
  };

  return (
    <div className="space-y-8 animate-fade-up" data-testid="plans-page">
      <div className="text-center">
        <h1 className="font-display font-extrabold tracking-tight text-3xl">Planos & Assinatura</h1>
        <p className="text-sm text-slate-400 mt-2">
          Plano atual: <span className="text-red-400 font-semibold" data-testid="current-plan">{PLAN_LABELS[user?.plan] || user?.plan}</span>
        </p>
      </div>

      <div className="flex items-center justify-center gap-3" data-testid="billing-toggle">
        <span className={`text-sm ${!yearly ? "text-slate-100 font-medium" : "text-slate-500"}`}>Mensal</span>
        <button
          onClick={() => setYearly(!yearly)}
          data-testid="billing-toggle-button"
          className={`w-12 h-6 rounded-full transition-colors relative ${yearly ? "bg-red-600" : "bg-slate-700"}`}
        >
          <span className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${yearly ? "translate-x-7" : "translate-x-1"}`} />
        </button>
        <span className={`text-sm ${yearly ? "text-slate-100 font-medium" : "text-slate-500"}`}>
          Anual <span className="text-emerald-400 text-xs font-semibold ml-1">−20%</span>
        </span>
      </div>

      <div className="grid md:grid-cols-3 gap-4 md:gap-6 max-w-5xl mx-auto">
        {PLANS.map((p) => {
          const price = yearly ? p.yearly : p.monthly;
          const lookupKey = `${p.id}_${yearly ? "yearly" : "monthly"}`;
          const isCurrent = user?.plan === p.id;
          return (
            <div key={p.id} className={`glass-card p-6 relative flex flex-col ${p.highlight ? "glow-border" : ""}`} data-testid={`plan-card-${p.id}`}>
              {p.highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-red-600 text-xs font-semibold flex items-center gap-1">
                  <Crown className="w-3 h-3" /> MAIS POPULAR
                </span>
              )}
              <h3 className="font-display font-semibold text-lg">{p.name}</h3>
              <p className="text-xs text-slate-500 mt-1">{p.desc}</p>
              <div className="mt-5 flex items-baseline gap-1">
                <span className="font-display font-extrabold text-3xl">{formatBRL(price)}</span>
                <span className="text-slate-500 text-sm">/{yearly ? "ano" : "mês"}</span>
              </div>
              <ul className="mt-6 space-y-3 flex-1">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-slate-300">
                    <Check className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" /> {f}
                  </li>
                ))}
              </ul>
              <Button
                onClick={() => checkout(p.id)}
                disabled={loading !== null || isCurrent}
                className={`w-full mt-8 rounded-full ${
                  isCurrent
                    ? "bg-white/5 text-slate-500 border border-slate-700 cursor-default"
                    : p.highlight
                      ? "bg-red-600 hover:bg-red-500 text-white"
                      : "bg-white/5 hover:bg-white/10 text-slate-200 border border-slate-700"
                }`}
                data-testid={`plan-checkout-${p.id}`}
              >
                {loading === lookupKey ? (
                  <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Abrindo checkout...</>
                ) : isCurrent ? (
                  "Plano atual"
                ) : (
                  `Assinar ${p.name}`
                )}
              </Button>
            </div>
          );
        })}
      </div>

      <p className="text-center text-xs text-slate-600 max-w-md mx-auto">
        Pagamento processado com segurança pelo Stripe. Cancele quando quiser. Nota fiscal emitida automaticamente.
      </p>
    </div>
  );
}
