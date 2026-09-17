import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Zap, Sparkles, BookOpen, BarChart3, Megaphone, Shield, ArrowRight, Check,
  TrendingUp, Clock, Layers, Bot, Instagram, Linkedin, Mail, CreditCard,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const STATS = [
  { value: "8x", label: "mais rápido para colocar uma peça no ar" },
  { value: "R$ 40M+", label: "em mídia sob gestão dos clientes" },
  { value: "20+", label: "clientes por workspace, sem virar planilha" },
  { value: "2", label: "modelos de fronteira: GPT-5.4 & Claude Sonnet 4.6" },
];

const FEATURES = [
  { icon: Sparkles, title: "Geração de peças com IA", desc: "Copy e criativos para Instagram, Meta Ads, LinkedIn e e-mail — já na voz de cada cliente." },
  { icon: BookOpen, title: "Bíblia da marca", desc: "Personas, tom de voz e playbooks indexados. A IA lê antes de escrever." },
  { icon: BarChart3, title: "Dashboard de indicadores", desc: "CTR, ROAS, gasto e conversões num painel tático de alta densidade." },
  { icon: Megaphone, title: "Piloto Meta Ads", desc: "Sincronize campanhas e leia performance sem trocar de aba." },
  { icon: Shield, title: "Alertas inteligentes", desc: "Regras sobre métricas críticas. A plataforma vigia o verbo por você." },
  { icon: Layers, title: "Multi-cliente real", desc: "Toda a carteira num workspace, com contexto de marca isolado por cliente." },
];

const INTEGRATIONS = [
  { icon: Bot, name: "GPT-5.4" }, { icon: Bot, name: "Claude Sonnet 4.6" },
  { icon: Megaphone, name: "Meta Ads" }, { icon: Instagram, name: "Instagram" },
  { icon: Linkedin, name: "LinkedIn" }, { icon: Mail, name: "E-mail" },
  { icon: CreditCard, name: "Stripe" }, { icon: BarChart3, name: "Analytics" },
];

const PLANS = [
  { name: "Starter Agência", price: "R$ 97", period: "/mês", features: ["5 clientes ativos", "50 gerações de IA/mês", "Bíblia da marca", "Dashboard de indicadores"] },
  { name: "Pro Scale", price: "R$ 197", period: "/mês", highlight: true, features: ["20 clientes ativos", "Gerações ilimitadas", "Imagens com IA incluídas", "Piloto Meta Ads", "Alertas inteligentes"] },
  { name: "Enterprise White-label", price: "R$ 397", period: "/mês", features: ["Clientes ilimitados", "White-label completo", "API dedicada", "Suporte prioritário"] },
];

function HeroMock() {
  return (
    <div className="glass-card glow-border p-4 sm:p-5">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-gradient-to-br from-red-500 to-rose-600 flex items-center justify-center">
            <Zap className="w-3.5 h-3.5 text-white" />
          </div>
          <span className="text-xs font-semibold text-slate-300">Cliente · Café Norte</span>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">Na voz da marca</span>
      </div>
      <div className="rounded-lg bg-[#0E0E11] border border-slate-800 p-4 text-sm text-slate-300 leading-relaxed">
        <p className="text-[11px] uppercase tracking-wider text-red-400 mb-2">Instagram · Carrossel</p>
        Seu café da manhã merece mais que pressa. ☕ Grãos torrados no ponto certo, entregues fresquinhos.
        <span className="text-slate-500"> Toque para conhecer o ritual Café Norte.</span>
      </div>
      <div className="grid grid-cols-3 gap-3 mt-4">
        {[["ROAS", "4,2x", "text-emerald-300"], ["CTR", "3,8%", "text-slate-200"], ["Gasto", "R$ 1,2k", "text-slate-200"]].map(([k, v, c]) => (
          <div key={k} className="rounded-lg bg-white/5 border border-slate-800 p-3">
            <p className="text-[10px] text-slate-500">{k}</p>
            <p className={`font-display font-bold text-lg ${c}`}>{v}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const [showStickyCta, setShowStickyCta] = useState(false);

  useEffect(() => {
    const onScroll = () => setShowStickyCta(window.scrollY > 560);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

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
          <nav className="hidden md:flex items-center gap-8 text-sm text-slate-400">
            <a href="#recursos" className="hover:text-white transition-colors" data-testid="nav-recursos">Recursos</a>
            <a href="#integracoes" className="hover:text-white transition-colors" data-testid="nav-integracoes">Integrações</a>
            <a href="#planos" className="hover:text-white transition-colors" data-testid="nav-planos">Planos</a>
          </nav>
          <div className="flex items-center gap-3">
            <Button onClick={() => navigate("/login")} className="bg-red-600 hover:bg-red-500 text-white rounded-full px-6" data-testid="landing-login-button">
              Entrar
            </Button>
          </div>
        </div>
      </header>

      {/* HERO */}
      <section className="relative max-w-6xl mx-auto px-6 pt-16 pb-20 lg:pt-24">
        <div className="absolute top-0 left-1/4 w-[600px] h-[380px] bg-red-600/20 blur-[150px] rounded-full pointer-events-none" />
        <div className="relative grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7 }}>
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-red-500/30 bg-red-500/10 text-red-300 text-xs font-medium mb-7">
              <Sparkles className="w-3.5 h-3.5" /> O cockpit de IA para agências de marketing
            </div>
            <h1 className="font-display font-extrabold tracking-tight text-4xl sm:text-5xl lg:text-6xl leading-[1.03]">
              Uma agência inteira <span className="bg-gradient-to-r from-red-400 via-rose-400 to-fuchsia-400 bg-clip-text text-transparent">operando por IA</span>.
            </h1>
            <p className="mt-6 text-base md:text-lg text-slate-400 max-w-xl leading-relaxed">
              Produza peças na voz de cada cliente, consulte a Bíblia da marca e leia o ROAS das campanhas —
              tudo num só lugar. Do briefing ao criativo no ar em minutos, não em dias.
            </p>
            <div className="mt-9 flex flex-wrap gap-4">
              <Button onClick={() => navigate("/login")} size="lg" className="bg-red-600 hover:bg-red-500 text-white rounded-full px-8 h-12 text-base" data-testid="hero-cta-button">
                Acessar plataforma <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
            <p className="mt-4 text-xs text-slate-500">Plataforma exclusiva para clientes Vanguarda.IA</p>
          </motion.div>

          <motion.div initial={{ opacity: 0, y: 40 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.15 }}>
            <HeroMock />
          </motion.div>
        </div>
      </section>

      {/* STATS BAND */}
      <section className="border-y border-slate-800/60 bg-white/[0.015]">
        <div className="max-w-6xl mx-auto px-6 py-10 grid grid-cols-2 lg:grid-cols-4 gap-8">
          {STATS.map((s, i) => (
            <motion.div key={s.label} initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5, delay: i * 0.06 }} data-testid={`stat-${i}`}>
              <p className="font-display font-extrabold text-3xl lg:text-4xl bg-gradient-to-r from-red-400 to-rose-400 bg-clip-text text-transparent">{s.value}</p>
              <p className="text-sm text-slate-400 mt-1 leading-snug">{s.label}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CAPABILITY SURFACES */}
      <section className="max-w-6xl mx-auto px-6 py-24 space-y-24">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-red-400">Produção</span>
            <h2 className="font-display font-bold tracking-tight text-3xl lg:text-4xl mt-3 leading-tight">Peças que já nascem na voz da marca</h2>
            <p className="text-slate-400 text-base mt-4 leading-relaxed max-w-lg">
              A IA lê a Bíblia do cliente antes de escrever: persona, tom, restrições e ofertas. O que sai já está no padrão — sem rodada infinita de ajuste.
            </p>
            <ul className="mt-6 space-y-3">
              {["Copy pronta para 6 formatos de canal", "Imagens de criativo com IA integrada", "Aprovação e histórico por cliente"].map((f) => (
                <li key={f} className="flex items-center gap-3 text-sm text-slate-300"><Check className="w-4 h-4 text-emerald-400 shrink-0" /> {f}</li>
              ))}
            </ul>
          </div>
          <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.6 }}>
            <HeroMock />
          </motion.div>
        </div>

        <div className="grid lg:grid-cols-2 gap-12 items-center">
          <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.6 }} className="order-2 lg:order-1">
            <div className="glass-card p-5">
              <div className="flex items-center justify-between mb-4">
                <span className="text-xs font-semibold text-slate-300 flex items-center gap-2"><TrendingUp className="w-4 h-4 text-red-400" /> Performance · últimos 30 dias</span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/10 text-red-300 border border-red-500/20">ao vivo</span>
              </div>
              <div className="flex items-end gap-2 h-32">
                {[40, 55, 48, 70, 62, 85, 78, 95].map((h, i) => (
                  <div key={i} className="flex-1 rounded-t bg-gradient-to-t from-red-600/40 to-red-400/80" style={{ height: `${h}%` }} />
                ))}
              </div>
              <div className="grid grid-cols-3 gap-3 mt-4">
                {[["ROAS médio", "4,6x"], ["Conversões", "1.284"], ["CPL", "R$ 8,40"]].map(([k, v]) => (
                  <div key={k} className="rounded-lg bg-white/5 border border-slate-800 p-3">
                    <p className="text-[10px] text-slate-500">{k}</p>
                    <p className="font-display font-bold text-base text-slate-100">{v}</p>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
          <div className="order-1 lg:order-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-red-400">Decisão</span>
            <h2 className="font-display font-bold tracking-tight text-3xl lg:text-4xl mt-3 leading-tight">Leia o ROAS antes de queimar verba</h2>
            <p className="text-slate-400 text-base mt-4 leading-relaxed max-w-lg">
              Indicadores de todas as campanhas num painel de alta densidade. Alertas disparam quando uma métrica sai da linha — você age antes do prejuízo, não depois do relatório.
            </p>
            <ul className="mt-6 space-y-3">
              {["Dashboard consolidado por cliente", "Regras de alerta sobre CTR, ROAS e gasto", "Sincronização com Meta Ads"].map((f) => (
                <li key={f} className="flex items-center gap-3 text-sm text-slate-300"><Check className="w-4 h-4 text-emerald-400 shrink-0" /> {f}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="recursos" className="max-w-6xl mx-auto px-6 py-20">
        <span className="text-xs font-semibold uppercase tracking-wider text-red-400">Plataforma</span>
        <h2 className="font-display font-bold tracking-tight text-3xl lg:text-4xl mt-3 mb-3">Um cockpit, não seis abas</h2>
        <p className="text-slate-400 text-base mb-12 max-w-xl">Da geração da peça à leitura do ROAS. Menos ferramentas soltas, mais campanha no ar.</p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {FEATURES.map((f, i) => (
            <motion.div key={f.title} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5, delay: i * 0.06 }}
              className="glass-card p-5 sm:p-6 transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-700" data-testid={`feature-card-${i}`}>
              <div className="w-10 h-10 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-4">
                <f.icon className="w-5 h-5 text-red-400" />
              </div>
              <h3 className="font-display font-semibold text-lg mb-2">{f.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* INTEGRATION WALL */}
      <section id="integracoes" className="max-w-6xl mx-auto px-6 py-16">
        <div className="glass-card p-8 lg:p-10">
          <div className="text-center mb-8">
            <h2 className="font-display font-bold tracking-tight text-2xl lg:text-3xl">Conecta com o stack que você já usa</h2>
            <p className="text-slate-400 text-sm mt-2">Modelos de fronteira e canais de mídia, prontos para plugar.</p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {INTEGRATIONS.map((it, i) => (
              <div key={it.name} className="flex items-center gap-3 rounded-lg bg-white/5 border border-slate-800 px-4 py-3 hover:border-slate-700 transition-colors" data-testid={`integration-${i}`}>
                <it.icon className="w-5 h-5 text-slate-300 shrink-0" />
                <span className="text-sm text-slate-300 truncate">{it.name}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* PRICING */}
      <section id="planos" className="max-w-6xl mx-auto px-6 py-20">
        <h2 className="font-display font-bold tracking-tight text-3xl lg:text-4xl mb-2 text-center">Planos para cada estágio da agência</h2>
        <p className="text-slate-400 text-base mb-12 text-center">Comece grátis. Escale quando a carteira crescer.</p>
        <div className="grid md:grid-cols-3 gap-4 md:gap-6 items-start">
          {PLANS.map((p, i) => (
            <div key={p.name} className={`glass-card p-6 relative ${p.highlight ? "glow-border md:-translate-y-2" : ""}`} data-testid={`landing-plan-${i}`}>
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
              <Button onClick={() => navigate("/login")}
                className={`w-full mt-8 rounded-full ${p.highlight ? "bg-red-600 hover:bg-red-500 text-white" : "bg-white/5 hover:bg-white/10 text-slate-200 border border-slate-700"}`}
                data-testid={`landing-plan-cta-${i}`}>
                Assinar {p.name}
              </Button>
            </div>
          ))}
        </div>
      </section>

      {/* FINAL CTA */}
      <section className="max-w-6xl mx-auto px-6 pb-24">
        <div className="glass-card glow-border p-10 lg:p-16 text-center relative overflow-hidden">
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[500px] h-[240px] bg-red-600/20 blur-[130px] rounded-full pointer-events-none" />
          <div className="relative">
            <div className="inline-flex items-center gap-2 text-xs text-slate-400 mb-5"><Clock className="w-3.5 h-3.5 text-red-400" /> Acesso exclusivo para clientes</div>
            <h2 className="font-display font-extrabold tracking-tight text-3xl lg:text-5xl leading-tight max-w-2xl mx-auto">
              Coloque sua agência no <span className="text-red-400">modo vanguarda</span> hoje.
            </h2>
            <Button onClick={() => navigate("/login")} size="lg" className="mt-8 bg-red-600 hover:bg-red-500 text-white rounded-full px-10 h-12 text-base" data-testid="final-cta-button">
              Acessar plataforma <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </div>
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

      {/* STICKY BOTTOM CTA */}
      <div className={`fixed bottom-0 inset-x-0 z-50 transition-transform duration-300 ${showStickyCta ? "translate-y-0" : "translate-y-full"}`} data-testid="sticky-cta-bar">
        <div className="backdrop-blur-xl bg-[#0B0B0D]/90 border-t border-slate-800">
          <div className="max-w-6xl mx-auto px-6 py-3 flex items-center justify-between gap-4">
            <p className="text-sm text-slate-300 hidden sm:block">Pronto para operar no modo vanguarda?</p>
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <Button onClick={() => navigate("/login")} className="bg-red-600 hover:bg-red-500 text-white rounded-full px-6 w-full sm:w-auto" data-testid="sticky-cta-button">Acessar plataforma</Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
