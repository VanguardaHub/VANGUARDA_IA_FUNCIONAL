import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Zap, Sparkles, BookOpen, BarChart3, Megaphone, Shield, ArrowRight, Check } from "lucide-react";
import { Button } from "@/components/ui/button";

const FEATURES = [
  { icon: Sparkles, title: "Geração de Peças com IA", desc: "Copies e criativos prontos para Instagram, Meta Ads, LinkedIn e e-mail — com GPT-5.4 Mini e Claude Sonnet 4.6." },
  { icon: BookOpen, title: "Bíblia da Marca", desc: "Base de conhecimento com busca inteligente: personas, guias de tom de voz e playbooks sempre à mão da IA." },
  { icon: BarChart3, title: "Dashboard de Indicadores", desc: "CTR, ROAS, gasto e conversões em tempo real num painel tático de alta densidade." },
  { icon: Megaphone, title: "Piloto Meta Ads", desc: "Sincronize campanhas e acompanhe performance sem sair da plataforma." },
  { icon: Shield, title: "Alertas Inteligentes", desc: "Regras de alerta sobre métricas críticas — a plataforma vigia suas campanhas por você." },
  { icon: Zap, title: "Multi-cliente", desc: "Gerencie toda a carteira da agência num único workspace, com contexto de marca por cliente." },
];

const PLANS = [
  { name: "Starter Agência", price: "R$ 97", period: "/mês", features: ["5 clientes ativos", "50 gerações de IA/mês", "Bíblia da marca", "Dashboard de indicadores"] },
  { name: "Pro Scale", price: "R$ 197", period: "/mês", highlight: true, features: ["20 clientes ativos", "Gerações ilimitadas", "Imagens com IA incluídas", "Piloto Meta Ads", "Alertas inteligentes"] },
  { name: "Enterprise White-label", price: "R$ 397", period: "/mês", features: ["Clientes ilimitados", "White-label completo", "API dedicada", "Suporte prioritário"] },
];

export default function Landing() {
  const navigate = useNavigate();
  return (
    <div className="min-h-screen bg-[#0B0B0D] text-slate-100 noise-overlay" data-testid="landing-page">
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-[#0B0B0D]/80 border-b border-slate-800/60">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <span className="font-display font-extrabold text-lg tracking-tight">Vanguarda<span className="text-red-400">.IA</span></span>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="ghost" onClick={() => navigate("/login")} className="text-slate-300 hover:text-white" data-testid="landing-login-button">
              Entrar
            </Button>
            <Button onClick={() => navigate("/register")} className="bg-red-600 hover:bg-red-500 text-white rounded-full px-5" data-testid="landing-signup-button">
              Começar grátis
            </Button>
          </div>
        </div>
      </header>

      <section className="relative max-w-6xl mx-auto px-6 pt-20 pb-24 lg:pt-28">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] bg-red-600/20 blur-[140px] rounded-full pointer-events-none" />
        <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }} className="relative">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-red-500/30 bg-red-500/10 text-red-300 text-xs font-medium mb-8">
            <Sparkles className="w-3.5 h-3.5" /> Plataforma de IA para agências de marketing
          </div>
          <h1 className="font-display font-extrabold tracking-tight text-4xl sm:text-5xl lg:text-6xl max-w-3xl leading-[1.05]">
            Sua agência no modo <span className="bg-gradient-to-r from-red-400 via-rose-400 to-fuchsia-400 bg-clip-text text-transparent">vanguarda</span>.
          </h1>
          <p className="mt-6 text-base md:text-lg text-slate-400 max-w-2xl leading-relaxed">
            Gere peças publicitárias com IA, consulte a Bíblia da marca e acompanhe indicadores de campanhas —
            tudo num único cockpit desenhado para operadores de agência.
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <Button onClick={() => navigate("/register")} size="lg" className="bg-red-600 hover:bg-red-500 text-white rounded-full px-8 h-12 text-base" data-testid="hero-cta-button">
              Criar conta grátis <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
            <Button onClick={() => navigate("/login")} size="lg" variant="outline" className="rounded-full px-8 h-12 text-base border-slate-700 text-slate-300 hover:bg-white/5" data-testid="hero-demo-button">
              Já tenho conta
            </Button>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.2 }} className="relative mt-16">
          <div className="glass-card glow-border p-2 overflow-hidden">
            <img
              src="https://images.unsplash.com/photo-1460925895917-afdab827c52f?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMzJ8MHwxfHNlYXJjaHwxfHxkaWdpdGFsJTIwbWFya2V0aW5nJTIwc3RyYXRlZ3klMjBhZ2VuY3klMjBtZXRyaWNzfGVufDB8fHx8MTc4OTU3Nzk5OXww&ixlib=rb-4.1.0&q=85"
              alt="Dashboard de métricas de marketing"
              className="rounded-lg w-full h-64 sm:h-96 object-cover"
              data-testid="hero-image"
            />
          </div>
        </motion.div>
      </section>

      <section className="max-w-6xl mx-auto px-6 py-20">
        <h2 className="font-display font-bold tracking-tight text-2xl lg:text-3xl mb-2">Um cockpit completo</h2>
        <p className="text-slate-400 text-base mb-12 max-w-xl">Da geração da peça à leitura do ROAS. Menos ferramentas, mais resultado.</p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: i * 0.08 }}
              className="glass-card p-5 sm:p-6 transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-700"
              data-testid={`feature-card-${i}`}
            >
              <div className="w-10 h-10 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-4">
                <f.icon className="w-5 h-5 text-red-400" />
              </div>
              <h3 className="font-display font-semibold text-lg mb-2">{f.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-6 py-20">
        <h2 className="font-display font-bold tracking-tight text-2xl lg:text-3xl mb-2 text-center">Planos para cada estágio da agência</h2>
        <p className="text-slate-400 text-base mb-12 text-center">Comece grátis. Escale quando precisar.</p>
        <div className="grid md:grid-cols-3 gap-4 md:gap-6">
          {PLANS.map((p, i) => (
            <div key={p.name} className={`glass-card p-6 relative ${p.highlight ? "glow-border" : ""}`} data-testid={`landing-plan-${i}`}>
              {p.highlight && (
                <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-red-600 text-xs font-semibold">MAIS POPULAR</span>
              )}
              <h3 className="font-display font-semibold text-lg">{p.name}</h3>
              <div className="mt-4 flex items-baseline gap-1">
                <span className="font-display font-extrabold text-3xl">{p.price}</span>
                <span className="text-slate-500 text-sm">{p.period}</span>
              </div>
              <ul className="mt-6 space-y-3">
                {p.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-slate-300">
                    <Check className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" /> {f}
                  </li>
                ))}
              </ul>
              <Button
                onClick={() => navigate("/register")}
                className={`w-full mt-8 rounded-full ${p.highlight ? "bg-red-600 hover:bg-red-500 text-white" : "bg-white/5 hover:bg-white/10 text-slate-200 border border-slate-700"}`}
                data-testid={`landing-plan-cta-${i}`}
              >
                Assinar {p.name}
              </Button>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-slate-800/60 py-10">
        <div className="max-w-6xl mx-auto px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Zap className="w-4 h-4 text-red-400" />
            <span className="font-display font-bold">Vanguarda.IA</span>
          </div>
          <p className="text-xs text-slate-500">© 2026 Vanguarda.IA — Inteligência para agências que lideram.</p>
        </div>
      </footer>
    </div>
  );
}
