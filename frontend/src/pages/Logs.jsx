import { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BellRing, Plus, Trash2, ScrollText, Activity } from "lucide-react";
import { toast } from "sonner";
import { format, parseISO } from "date-fns";

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
const KIND_LABELS = {
  geracao: "Geração IA", meta: "Meta Ads", cliente: "Cliente", biblia: "Bíblia",
  alerta: "Alerta", peca: "Peça", auth: "Acesso", config: "Config",
};
const METRIC_LABELS = { spend: "Investimento (R$)", ctr: "CTR (%)", roas: "ROAS (x)", conversions: "Conversões" };

export default function Logs() {
  const [data, setData] = useState({ logs: [], occurrences: [] });
  const [rules, setRules] = useState([]);
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", metric: "ctr", operator: "lt", threshold: 1.2 });

  const load = () => {
    api.get("/logs").then(({ data }) => setData(data)).catch(() => {});
    api.get("/alerts/rules").then(({ data }) => setRules(data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const addRule = async (e) => {
    e.preventDefault();
    try {
      await api.post("/alerts/rules", { ...form, threshold: parseFloat(form.threshold) });
      toast.success("Regra de alerta criada");
      setOpen(false);
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const removeRule = async (id) => {
    try {
      await api.delete(`/alerts/rules/${id}`);
      toast.success("Regra removida");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const kinds = [...new Set(data.logs.map((l) => l.kind))];
  const filtered = filter === "all" ? data.logs : data.logs.filter((l) => l.kind === filter);

  return (
    <div className="space-y-6 animate-fade-up" data-testid="logs-page">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display font-extrabold tracking-tight text-3xl">Logs & Alertas</h1>
          <p className="text-sm text-slate-400 mt-1">Timeline da operação e regras de monitoramento</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-amber-600 hover:bg-amber-500 text-white rounded-full" data-testid="new-rule-button">
              <Plus className="w-4 h-4 mr-2" /> Nova regra de alerta
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#15151A] border-slate-800 text-slate-100" data-testid="new-rule-dialog">
            <DialogHeader>
              <DialogTitle className="font-display">Regra de alerta</DialogTitle>
            </DialogHeader>
            <form onSubmit={addRule} className="space-y-4">
              <div className="space-y-2">
                <Label className="text-slate-300">Nome *</Label>
                <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="bg-[#0E0E11] border-slate-700" placeholder="CTR abaixo do saudável" data-testid="rule-name-input" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="space-y-2">
                  <Label className="text-slate-300">Métrica</Label>
                  <Select value={form.metric} onValueChange={(v) => setForm({ ...form, metric: v })}>
                    <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="rule-metric-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                      {Object.entries(METRIC_LABELS).map(([k, v]) => (
                        <SelectItem key={k} value={k}>{v}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Condição</Label>
                  <Select value={form.operator} onValueChange={(v) => setForm({ ...form, operator: v })}>
                    <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="rule-operator-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                      <SelectItem value="gt">Acima de</SelectItem>
                      <SelectItem value="lt">Abaixo de</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Limite</Label>
                  <Input type="number" step="0.01" required value={form.threshold}
                    onChange={(e) => setForm({ ...form, threshold: e.target.value })}
                    className="bg-[#0E0E11] border-slate-700" data-testid="rule-threshold-input" />
                </div>
              </div>
              <Button type="submit" className="w-full bg-amber-600 hover:bg-amber-500 text-white" data-testid="rule-submit-button">
                Criar regra
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 md:gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex gap-2 flex-wrap" data-testid="logs-filters">
            <button onClick={() => setFilter("all")} data-testid="filter-all"
              className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                filter === "all" ? "bg-red-500/10 text-red-300 border-red-500/30" : "text-slate-400 border-slate-800 hover:border-slate-700"
              }`}>
              Todos
            </button>
            {kinds.map((k) => (
              <button key={k} onClick={() => setFilter(k)} data-testid={`filter-${k}`}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                  filter === k ? "bg-red-500/10 text-red-300 border-red-500/30" : "text-slate-400 border-slate-800 hover:border-slate-700"
                }`}>
                {KIND_LABELS[k] || k}
              </button>
            ))}
          </div>

          <div className="glass-card p-5" data-testid="logs-timeline">
            <h3 className="font-display font-semibold text-lg mb-4 flex items-center gap-2">
              <Activity className="w-4 h-4 text-red-400" /> Timeline de atividade
            </h3>
            {filtered.length === 0 ? (
              <p className="text-sm text-slate-500">Nenhum evento neste filtro.</p>
            ) : (
              <div className="space-y-1 max-h-[560px] overflow-y-auto pr-2">
                {filtered.map((log) => (
                  <div key={log.id} className="flex items-start gap-3 py-2.5 border-b border-slate-800/40 last:border-0" data-testid={`log-${log.id}`}>
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold uppercase border shrink-0 mt-0.5 ${KIND_COLORS[log.kind] || KIND_COLORS.auth}`}>
                      {KIND_LABELS[log.kind] || log.kind}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-300">{log.message}</p>
                      <p className="text-xs text-slate-600 font-mono">{format(parseISO(log.created_at), "dd/MM/yyyy HH:mm:ss")}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="glass-card p-5" data-testid="alert-rules-panel">
            <h3 className="font-display font-semibold text-lg mb-4 flex items-center gap-2">
              <ScrollText className="w-4 h-4 text-amber-400" /> Regras ativas
            </h3>
            {rules.length === 0 ? (
              <p className="text-sm text-slate-500">Nenhuma regra configurada.</p>
            ) : (
              <div className="space-y-3">
                {rules.map((r) => (
                  <div key={r.id} className="flex items-center justify-between gap-2 p-3 rounded-lg bg-white/[0.02] border border-slate-800 group" data-testid={`rule-${r.id}`}>
                    <div>
                      <p className="text-sm font-medium">{r.name}</p>
                      <p className="text-xs text-slate-500 font-mono">
                        {METRIC_LABELS[r.metric]} {r.operator === "gt" ? ">" : "<"} {r.threshold}
                      </p>
                    </div>
                    <button onClick={() => removeRule(r.id)} data-testid={`rule-delete-${r.id}`}
                      className="opacity-0 group-hover:opacity-100 transition-opacity p-1.5 rounded-lg hover:bg-rose-500/10 text-slate-500 hover:text-rose-400">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="glass-card p-5" data-testid="alert-occurrences-panel">
            <h3 className="font-display font-semibold text-lg mb-4 flex items-center gap-2">
              <BellRing className="w-4 h-4 text-rose-400" /> Alertas disparados
            </h3>
            {data.occurrences.length === 0 ? (
              <p className="text-sm text-slate-500">Nenhum alerta disparado. Tudo sob controle.</p>
            ) : (
              <div className="space-y-3">
                {data.occurrences.map((o) => (
                  <div key={o.id} className="p-3 rounded-lg bg-rose-500/5 border border-rose-500/20" data-testid={`occurrence-${o.id}`}>
                    <p className="text-sm font-medium text-rose-300">{o.rule_name}</p>
                    <p className="text-xs text-slate-400 mt-1">{o.campaign_name}</p>
                    <p className="text-xs text-slate-500 font-mono mt-1">
                      {METRIC_LABELS[o.metric]}: {o.value} (limite: {o.threshold})
                    </p>
                    <p className="text-[10px] text-slate-600 font-mono mt-1">{format(parseISO(o.created_at), "dd/MM/yyyy HH:mm")}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
