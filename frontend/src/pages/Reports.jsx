import { useEffect, useState } from "react";
import { api, formatBRLPrecise } from "@/lib/api";
import { Receipt, TrendingUp, Layers, RefreshCw } from "lucide-react";

function StatCard({ icon: Icon, label, value, sub, accent = "text-red-400", testid }) {
  return (
    <div className="glass-card p-5" data-testid={testid}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs text-slate-500 uppercase tracking-wider font-medium">{label}</span>
        <Icon className={`w-4 h-4 ${accent}`} />
      </div>
      <p className="font-display font-extrabold text-2xl tracking-tight">{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
  );
}

export default function Reports() {
  const [data, setData] = useState(null);

  useEffect(() => {
    api.get("/reports/costs").then(({ data }) => setData(data)).catch(() => {});
  }, []);

  if (!data)
    return (
      <div className="flex items-center justify-center h-64" data-testid="reports-loading">
        <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );

  const margin = data.total_billable_brl - data.total_cost_brl;

  return (
    <div className="space-y-6 animate-fade-up" data-testid="reports-page">
      <div>
        <h1 className="font-display font-extrabold tracking-tight text-3xl">Custos & Faturamento</h1>
        <p className="text-sm text-slate-400 mt-1">Custo de IA por cliente — base para o faturamento da agência (markup {data.markup_pct}%)</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard icon={Receipt} label="Custo interno (IA)" value={formatBRLPrecise(data.total_cost_brl)} sub="soma de todas as etapas" accent="text-amber-400" testid="report-total-cost" />
        <StatCard icon={TrendingUp} label="A faturar (com markup)" value={formatBRLPrecise(data.total_billable_brl)} sub="preço sugerido ao cliente" accent="text-emerald-400" testid="report-total-billable" />
        <StatCard icon={Layers} label="Margem bruta" value={formatBRLPrecise(margin)} sub="faturar − custo" accent="text-red-400" testid="report-margin" />
      </div>

      <div className="glass-card overflow-hidden" data-testid="report-table">
        <div className="p-5 border-b border-slate-800/60 flex items-center gap-2">
          <RefreshCw className="w-4 h-4 text-slate-500" />
          <h3 className="font-display font-semibold">Detalhamento por cliente</h3>
        </div>
        {data.rows.length === 0 ? (
          <p className="p-8 text-center text-sm text-slate-500" data-testid="report-empty">
            Ainda não há custos de IA registrados. Gere peças para começar a acompanhar.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-left text-xs text-slate-500 uppercase tracking-wider">
                  <th className="p-4">Cliente</th>
                  <th className="p-4 text-right">Peças</th>
                  <th className="p-4 text-right">Refações</th>
                  <th className="p-4 text-right">Custo interno</th>
                  <th className="p-4 text-right">A faturar</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.client_id} className="border-b border-slate-800/50 hover:bg-white/[0.02]" data-testid={`report-row-${r.client_id}`}>
                    <td className="p-4 font-medium">{r.client_name}</td>
                    <td className="p-4 text-right font-mono text-slate-300">{r.pieces}</td>
                    <td className="p-4 text-right font-mono text-slate-300">{r.refacoes}</td>
                    <td className="p-4 text-right font-mono text-amber-300">{formatBRLPrecise(r.cost_brl)}</td>
                    <td className="p-4 text-right font-mono text-emerald-300">{formatBRLPrecise(r.billable_brl)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
