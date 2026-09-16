import { useEffect, useState } from "react";
import { api, formatBRL, formatNumber } from "@/lib/api";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar } from "recharts";
import { Users, Sparkles, Megaphone, TrendingUp, MousePointerClick, DollarSign, Target, Activity } from "lucide-react";
import { format, parseISO } from "date-fns";
import { ptBR } from "date-fns/locale";

const KIND_COLORS = {
  geracao: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  meta: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  cliente: "bg-red-500/10 text-red-400 border-red-500/20",
  biblia: "bg-rose-500/10 text-rose-400 border-rose-500/20",
  alerta: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  peca: "bg-fuchsia-500/10 text-fuchsia-400 border-fuchsia-500/20",
  auth: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  config: "bg-slate-500/10 text-slate-400 border-slate-500/20",
};

function KpiCard({ icon: Icon, label, value, sub, testid, accent = "text-red-400" }) {
  return (
    <div className="glass-card p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-700" data-testid={testid}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-500 uppercase tracking-wider font-medium">{label}</span>
        <Icon className={`w-4 h-4 ${accent}`} />
      </div>
      <p className="font-display font-extrabold text-2xl tracking-tight">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/dashboard").then(({ data }) => setData(data)).catch(() => {});
  }, []);

  if (!data)
    return (
      <div className="flex items-center justify-center h-64" data-testid="dashboard-loading">
        <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );

  const { kpis, series, recent_activity } = data;

  return (
    <div className="space-y-6 animate-fade-up" data-testid="dashboard-page">
      <div>
        <h1 className="font-display font-extrabold tracking-tight text-3xl">Visão Geral</h1>
        <p className="text-sm text-slate-400 mt-1">Indicadores consolidados da operação — últimos 30 dias</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard icon={DollarSign} label="Investimento" value={formatBRL(kpis.spend)} sub="em mídia paga" testid="kpi-spend" accent="text-emerald-400" />
        <KpiCard icon={TrendingUp} label="ROAS" value={`${kpis.roas}x`} sub={`${formatBRL(kpis.revenue)} em receita`} testid="kpi-roas" accent="text-red-400" />
        <KpiCard icon={MousePointerClick} label="CTR médio" value={`${kpis.ctr}%`} sub={`${formatNumber(kpis.clicks)} cliques`} testid="kpi-ctr" accent="text-amber-400" />
        <KpiCard icon={Target} label="Conversões" value={formatNumber(kpis.conversions)} sub={`${formatNumber(kpis.impressions)} impressões`} testid="kpi-conversions" accent="text-fuchsia-400" />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard icon={Users} label="Clientes" value={kpis.clients} sub="na carteira" testid="kpi-clients" />
        <KpiCard icon={Megaphone} label="Campanhas ativas" value={kpis.active_campaigns} sub={`de ${kpis.total_campaigns} no total`} testid="kpi-campaigns" />
        <KpiCard icon={Sparkles} label="Peças geradas" value={kpis.pieces} sub="com IA" testid="kpi-pieces" />
        <KpiCard icon={Activity} label="Impressões" value={formatNumber(kpis.impressions)} sub="alcance total" testid="kpi-impressions" />
      </div>

      <div className="grid lg:grid-cols-3 gap-4 md:gap-6">
        <div className="glass-card p-5 sm:p-6 lg:col-span-2" data-testid="chart-spend">
          <h3 className="font-display font-semibold text-lg mb-1">Investimento diário</h3>
          <p className="text-xs text-slate-500 mb-4">Gasto consolidado por dia</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series}>
                <defs>
                  <linearGradient id="gradSpend" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FF2D40" stopOpacity={0.4} />
                    <stop offset="100%" stopColor="#FF2D40" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tickFormatter={(d) => format(parseISO(d), "dd/MM", { locale: ptBR })}
                  tick={{ fill: "#64748B", fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={30} />
                <YAxis tick={{ fill: "#64748B", fontSize: 11 }} axisLine={false} tickLine={false}
                  tickFormatter={(v) => `R$${v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v}`} />
                <Tooltip
                  contentStyle={{ background: "#15151A", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12 }}
                  labelFormatter={(d) => format(parseISO(d), "dd 'de' MMMM", { locale: ptBR })}
                  formatter={(v) => [formatBRL(v), "Investimento"]}
                />
                <Area type="monotone" dataKey="spend" stroke="#FF2D40" strokeWidth={2} fill="url(#gradSpend)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="glass-card p-5 sm:p-6" data-testid="chart-conversions">
          <h3 className="font-display font-semibold text-lg mb-1">Conversões</h3>
          <p className="text-xs text-slate-500 mb-4">Por dia</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={series.slice(-14)}>
                <XAxis dataKey="date" tickFormatter={(d) => format(parseISO(d), "dd/MM")}
                  tick={{ fill: "#64748B", fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: "#15151A", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12, fontSize: 12 }}
                  formatter={(v) => [v, "Conversões"]}
                />
                <Bar dataKey="conversions" fill="#10B981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="glass-card p-5 sm:p-6" data-testid="recent-activity">
        <h3 className="font-display font-semibold text-lg mb-4">Atividade recente</h3>
        {recent_activity.length === 0 ? (
          <p className="text-sm text-slate-500">Nenhuma atividade ainda. Comece gerando sua primeira peça com IA.</p>
        ) : (
          <div className="space-y-3">
            {recent_activity.map((log) => (
              <div key={log.id} className="flex items-start gap-3" data-testid={`activity-${log.id}`}>
                <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase border shrink-0 mt-0.5 ${KIND_COLORS[log.kind] || KIND_COLORS.auth}`}>
                  {log.kind}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-300 truncate">{log.message}</p>
                  <p className="text-xs text-slate-600 font-mono">{format(parseISO(log.created_at), "dd/MM/yyyy HH:mm")}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
