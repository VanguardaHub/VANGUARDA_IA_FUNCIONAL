import { useEffect, useState } from "react";
import { api, formatApiError, formatBRL, formatNumber } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, RefreshCw, Loader2, Megaphone, LayoutGrid, Table as TableIcon, Send, CalendarClock } from "lucide-react";
import { toast } from "sonner";

const STATUS_STYLES = {
  ativa: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  pausada: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  em_analise: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  agendada: "bg-violet-500/10 text-violet-300 border-violet-500/20",
};
const STATUS_LABELS = { ativa: "Ativa", pausada: "Pausada", em_analise: "Em análise", agendada: "Agendada" };

function RoasDial({ roas }) {
  const pct = Math.min(roas / 6, 1);
  const color = roas >= 3 ? "#10B981" : roas >= 1.5 ? "#F59E0B" : "#F43F5E";
  return (
    <div className="relative w-20 h-20">
      <svg viewBox="0 0 80 80" className="w-20 h-20 -rotate-90">
        <circle cx="40" cy="40" r="34" fill="none" stroke="#1F1F26" strokeWidth="7" />
        <circle cx="40" cy="40" r="34" fill="none" stroke={color} strokeWidth="7"
          strokeDasharray={`${pct * 213.6} 213.6`} strokeLinecap="round" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="font-mono font-semibold text-sm" style={{ color }}>{roas}x</span>
        <span className="text-[9px] text-slate-500 uppercase">ROAS</span>
      </div>
    </div>
  );
}

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([]);
  const [clients, setClients] = useState([]);
  const [view, setView] = useState("grid");
  const [open, setOpen] = useState(false);
  const [syncing, setSyncing] = useState(null);
  const [form, setForm] = useState({ client_id: "", name: "", objective: "Conversões", budget_daily: 100 });
  const [scheduleTarget, setScheduleTarget] = useState(null);
  const [scheduleAt, setScheduleAt] = useState("");
  const minDateTime = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);

  const load = () => {
    api.get("/campaigns").then(({ data }) => setCampaigns(data)).catch(() => {});
    api.get("/clients").then(({ data }) => setClients(data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    try {
      await api.post("/campaigns", { ...form, budget_daily: parseFloat(form.budget_daily) });
      toast.success("Campanha criada (piloto Meta Ads)");
      setOpen(false);
      setForm({ client_id: "", name: "", objective: "Conversões", budget_daily: 100 });
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const sync = async (id) => {
    setSyncing(id);
    try {
      await api.post(`/campaigns/${id}/sync`);
      toast.success("Sincronização Meta Ads concluída");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSyncing(null);
    }
  };

  const toggleStatus = async (id, current) => {
    const next = current === "ativa" ? "pausada" : "ativa";
    try {
      await api.post(`/campaigns/${id}/status`, { status: next });
      toast.success(`Campanha ${next === "ativa" ? "ativada" : "pausada"}`);
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const publishNow = async (id) => {
    try {
      await api.post(`/campaigns/${id}/publish`, {});
      toast.success("Campanha publicada!");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const doSchedule = async () => {
    if (!scheduleAt) { toast.error("Escolha data e hora"); return; }
    try {
      await api.post(`/campaigns/${scheduleTarget}/publish`, { scheduled_at: new Date(scheduleAt).toISOString() });
      toast.success("Campanha agendada!");
      setScheduleTarget(null); setScheduleAt("");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  return (
    <div className="space-y-6 animate-fade-up" data-testid="campaigns-page">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display font-extrabold tracking-tight text-3xl">Campanhas</h1>
          <p className="text-sm text-slate-400 mt-1 flex items-center gap-2">
            Piloto Meta Ads
            <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">BETA</span>
          </p>
        </div>
        <div className="flex gap-3">
          <div className="flex rounded-lg border border-slate-800 overflow-hidden">
            <button onClick={() => setView("grid")} data-testid="view-grid-button"
              className={`p-2.5 transition-colors ${view === "grid" ? "bg-red-500/10 text-red-300" : "text-slate-500 hover:text-slate-300"}`}>
              <LayoutGrid className="w-4 h-4" />
            </button>
            <button onClick={() => setView("table")} data-testid="view-table-button"
              className={`p-2.5 transition-colors ${view === "table" ? "bg-red-500/10 text-red-300" : "text-slate-500 hover:text-slate-300"}`}>
              <TableIcon className="w-4 h-4" />
            </button>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-red-600 hover:bg-red-500 text-white rounded-full" data-testid="new-campaign-button">
                <Plus className="w-4 h-4 mr-2" /> Nova campanha
              </Button>
            </DialogTrigger>
            <DialogContent className="bg-[#15151A] border-slate-800 text-slate-100" data-testid="new-campaign-dialog">
              <DialogHeader>
                <DialogTitle className="font-display">Nova campanha — piloto Meta Ads</DialogTitle>
              </DialogHeader>
              <form onSubmit={submit} className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-slate-300">Cliente *</Label>
                  <Select value={form.client_id} onValueChange={(v) => setForm({ ...form, client_id: v })} required>
                    <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="campaign-client-select">
                      <SelectValue placeholder="Selecione" />
                    </SelectTrigger>
                    <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                      {clients.map((c) => (
                        <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Nome da campanha *</Label>
                  <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="bg-[#0E0E11] border-slate-700" placeholder="Conversões — Black Friday" data-testid="campaign-name-input" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label className="text-slate-300">Objetivo</Label>
                    <Select value={form.objective} onValueChange={(v) => setForm({ ...form, objective: v })}>
                      <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="campaign-objective-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                        {["Conversões", "Tráfego", "Remarketing", "Reconhecimento", "Leads"].map((o) => (
                          <SelectItem key={o} value={o}>{o}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label className="text-slate-300">Orçamento diário (R$)</Label>
                    <Input type="number" min="1" step="0.01" value={form.budget_daily}
                      onChange={(e) => setForm({ ...form, budget_daily: e.target.value })}
                      className="bg-[#0E0E11] border-slate-700" data-testid="campaign-budget-input" />
                  </div>
                </div>
                <Button type="submit" className="w-full bg-red-600 hover:bg-red-500 text-white" data-testid="campaign-submit-button">
                  Criar campanha
                </Button>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {campaigns.length === 0 ? (
        <div className="glass-card p-12 text-center" data-testid="campaigns-empty">
          <Megaphone className="w-10 h-10 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400">Nenhuma campanha. Crie a primeira para o piloto Meta Ads.</p>
        </div>
      ) : view === "grid" ? (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {campaigns.map((c) => (
            <div key={c.id} className="glass-card p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-700" data-testid={`campaign-card-${c.id}`}>
              <div className="flex items-start justify-between gap-3 mb-3">
                <div className="min-w-0">
                  <h3 className="font-display font-semibold truncate">{c.name}</h3>
                  <p className="text-xs text-slate-500">{c.client_name} · {c.objective}</p>
                </div>
                <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border shrink-0 ${STATUS_STYLES[c.status]}`}>
                  {STATUS_LABELS[c.status]}
                </span>
              </div>
              <p className="text-xs text-slate-600 font-mono mb-4">{c.ad_account_id}</p>
              <div className="flex items-center gap-4">
                <RoasDial roas={c.totals.roas} />
                <div className="space-y-1.5 text-xs flex-1">
                  <div className="flex justify-between"><span className="text-slate-500">Orçamento/dia</span><span className="font-mono text-slate-200" data-testid={`campaign-budget-${c.id}`}>{formatBRL(c.budget_daily)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Investido</span><span className="font-mono text-slate-200">{formatBRL(c.totals.spend)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Impressões</span><span className="font-mono text-slate-200">{formatNumber(c.totals.impressions)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">CTR</span><span className="font-mono text-slate-200">{c.totals.ctr}%</span></div>
                  <div className="flex justify-between"><span className="text-slate-500">Conversões</span><span className="font-mono text-slate-200">{formatNumber(c.totals.conversions)}</span></div>
                </div>
              </div>
              <div className="flex gap-2 mt-4">
                <Button size="sm" onClick={() => publishNow(c.id)}
                  className="flex-1 bg-red-600 hover:bg-red-500 text-white" data-testid={`campaign-publish-${c.id}`}>
                  <Send className="w-3.5 h-3.5 mr-1.5" /> Publicar
                </Button>
                <Button size="sm" variant="outline" onClick={() => { setScheduleTarget(c.id); setScheduleAt(""); }}
                  title="Agendar publicação" aria-label="Agendar publicação"
                  className="border-slate-700 bg-white/5 hover:bg-white/10 text-slate-200" data-testid={`campaign-schedule-${c.id}`}>
                  <CalendarClock className="w-3.5 h-3.5" />
                </Button>
              </div>
              <div className="flex gap-2 mt-2">
                <Button size="sm" variant="outline" onClick={() => sync(c.id)} disabled={syncing === c.id}
                  className="flex-1 border-slate-700 bg-white/5 hover:bg-white/10 text-slate-200" data-testid={`campaign-sync-${c.id}`}>
                  {syncing === c.id ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 mr-1.5" />}
                  Sincronizar
                </Button>
                <Button size="sm" variant="outline" onClick={() => toggleStatus(c.id, c.status)}
                  className="border-slate-700 bg-white/5 hover:bg-white/10 text-slate-200" data-testid={`campaign-toggle-${c.id}`}>
                  {c.status === "ativa" ? "Pausar" : "Ativar"}
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="glass-card overflow-hidden" data-testid="campaigns-table">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-left text-xs text-slate-500 uppercase tracking-wider">
                <th className="p-4">Campanha</th>
                <th className="p-4">Cliente</th>
                <th className="p-4">Status</th>
                <th className="p-4 text-right">Orçamento/dia</th>
                <th className="p-4 text-right">Investido</th>
                <th className="p-4 text-right">CTR</th>
                <th className="p-4 text-right">ROAS</th>
                <th className="p-4"></th>
              </tr>
            </thead>
            <tbody>
              {campaigns.map((c) => (
                <tr key={c.id} className="border-b border-slate-800/50 hover:bg-white/[0.02]" data-testid={`campaign-row-${c.id}`}>
                  <td className="p-4 font-medium">{c.name}</td>
                  <td className="p-4 text-slate-400">{c.client_name}</td>
                  <td className="p-4">
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${STATUS_STYLES[c.status]}`}>
                      {STATUS_LABELS[c.status]}
                    </span>
                  </td>
                  <td className="p-4 text-right font-mono">{formatBRL(c.budget_daily)}</td>
                  <td className="p-4 text-right font-mono">{formatBRL(c.totals.spend)}</td>
                  <td className="p-4 text-right font-mono">{c.totals.ctr}%</td>
                  <td className="p-4 text-right font-mono">{c.totals.roas}x</td>
                  <td className="p-4 text-right">
                    <Button size="sm" variant="ghost" onClick={() => sync(c.id)} disabled={syncing === c.id} title="Sincronizar Meta Ads" aria-label="Sincronizar Meta Ads" data-testid={`campaign-sync-row-${c.id}`}>
                      {syncing === c.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Dialog open={!!scheduleTarget} onOpenChange={(o) => { if (!o) { setScheduleTarget(null); setScheduleAt(""); } }}>
        <DialogContent className="bg-[#15151A] border-slate-800 text-slate-100" data-testid="campaign-schedule-dialog">
          <DialogHeader>
            <DialogTitle className="font-display">Agendar publicação</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-slate-300">Data e hora</Label>
              <Input type="datetime-local" min={minDateTime} value={scheduleAt} onChange={(e) => setScheduleAt(e.target.value)}
                className="bg-[#0E0E11] border-slate-700" data-testid="campaign-schedule-input" />
            </div>
            <Button onClick={doSchedule} className="w-full bg-red-600 hover:bg-red-500 text-white" data-testid="campaign-schedule-confirm">
              <CalendarClock className="w-4 h-4 mr-2" /> Agendar campanha
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
