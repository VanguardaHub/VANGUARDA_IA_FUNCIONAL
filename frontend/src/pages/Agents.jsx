import { useEffect, useState } from "react";
import { api, formatApiError, formatBRLPrecise } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Bot, Share2, Magnet, Target, Mail, Loader2, Check, X, Trash2, Play, Clock, CheckCircle2 } from "lucide-react";
import { toast } from "sonner";
import { format, parseISO } from "date-fns";

const ICONS = { social: Share2, inbound: Magnet, midia_paga: Target, account: Mail };
const MODELS = [
  { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { id: "gpt-5.4-mini", label: "GPT-5.4 Mini" },
];
const STATUS = {
  pendente: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  aprovado: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  rejeitado: "bg-slate-500/10 text-slate-400 border-slate-500/20",
};

export default function Agents() {
  const [agents, setAgents] = useState([]);
  const [clients, setClients] = useState([]);
  const [proposals, setProposals] = useState([]);
  const [filter, setFilter] = useState("all");
  const [active, setActive] = useState(null);
  const [form, setForm] = useState({ client_id: "", model: "claude-sonnet-4-6", instructions: "", quantity: 5 });
  const [running, setRunning] = useState(false);
  const [busyId, setBusyId] = useState(null);

  const loadProps = () => api.get("/agents/proposals").then(({ data }) => setProposals(data)).catch(() => {});
  useEffect(() => {
    api.get("/agents").then(({ data }) => setAgents(data)).catch(() => {});
    api.get("/clients").then(({ data }) => setClients(data)).catch(() => {});
    loadProps();
  }, []);

  const openRun = (agent) => {
    setActive(agent);
    setForm({ client_id: clients[0]?.id || "", model: "claude-sonnet-4-6", instructions: "", quantity: 5 });
  };

  const run = async () => {
    if (!form.client_id) { toast.error("Selecione um cliente"); return; }
    setRunning(true);
    try {
      await api.post(`/agents/${active.key}/run`, form);
      toast.success("Proposta gerada! Revise e aprove abaixo.");
      setActive(null);
      loadProps();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setRunning(false);
    }
  };

  const approve = async (id) => {
    setBusyId(id);
    try {
      const { data } = await api.post(`/agents/proposals/${id}/approve`);
      const r = data.result || {};
      const msg = r.created_pieces != null ? `${r.created_pieces} peça(s) criada(s)`
        : r.created_campaigns != null ? `${r.created_campaigns} campanha(s) criada(s)`
        : r.email_id ? `E-mail enviado para ${r.to}` : "Ação executada";
      setProposals((prev) => prev.map((x) => (x.id === id ? data : x)));
      toast.success(`Aprovado — ${msg}`);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setBusyId(null);
    }
  };

  const reject = async (id) => {
    try {
      await api.post(`/agents/proposals/${id}/reject`);
      setProposals((prev) => prev.map((x) => (x.id === id ? { ...x, status: "rejeitado" } : x)));
      toast.success("Proposta rejeitada");
    } catch (err) { toast.error(formatApiError(err)); }
  };
  const remove = async (id) => {
    try {
      await api.delete(`/agents/proposals/${id}`);
      setProposals((prev) => prev.filter((x) => x.id !== id));
    } catch (err) { toast.error(formatApiError(err)); }
  };

  const filtered = filter === "all" ? proposals : proposals.filter((p) => p.status === filter);

  return (
    <div className="space-y-6 animate-fade-up" data-testid="agents-page">
      <div>
        <h1 className="font-display font-extrabold tracking-tight text-3xl">Agentes Operacionais</h1>
        <p className="text-sm text-slate-400 mt-1">Cada agente propõe uma ação — nada é executado sem sua aprovação (validação humana)</p>
      </div>

      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {agents.map((a) => {
          const Icon = ICONS[a.key] || Bot;
          return (
            <div key={a.key} className="glass-card p-5 flex flex-col" data-testid={`agent-card-${a.key}`}>
              <div className="w-10 h-10 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-3">
                <Icon className="w-5 h-5 text-red-400" />
              </div>
              <h3 className="font-display font-semibold">{a.label}</h3>
              <p className="text-xs text-slate-500 mt-1 flex-1">{a.desc}</p>
              <p className="text-[11px] text-slate-600 mt-2 mb-3">{a.action}</p>
              <Button size="sm" onClick={() => openRun(a)} className="bg-red-600 hover:bg-red-500 text-white rounded-full" data-testid={`agent-run-${a.key}`}>
                <Play className="w-3.5 h-3.5 mr-1.5" /> Rodar agente
              </Button>
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="font-display font-bold text-xl flex items-center gap-2"><Clock className="w-5 h-5 text-amber-400" /> Fila de aprovação</h2>
        <div className="flex gap-2">
          {["all", "pendente", "aprovado", "rejeitado"].map((s) => (
            <button key={s} onClick={() => setFilter(s)} data-testid={`proposals-filter-${s}`}
              className={`px-3 py-1.5 rounded-full text-xs font-medium border capitalize transition-colors ${
                filter === s ? "bg-red-500/10 text-red-300 border-red-500/30" : "text-slate-400 border-slate-800 hover:border-slate-700"
              }`}>{s === "all" ? "Todas" : s}</button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="glass-card p-12 text-center text-slate-500 text-sm" data-testid="proposals-empty">
          Nenhuma proposta {filter !== "all" ? filter : "ainda"}. Rode um agente acima para começar.
        </div>
      ) : (
        <div className="space-y-3" data-testid="proposals-list">
          {filtered.map((p) => (
            <div key={p.id} className="glass-card p-5" data-testid={`proposal-${p.id}`}>
              <div className="flex items-start gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <h3 className="font-display font-semibold">{p.title}</h3>
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border capitalize ${STATUS[p.status]}`} data-testid={`proposal-status-${p.id}`}>{p.status}</span>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-mono border bg-white/5 border-slate-700 text-slate-400">{p.agent_label}</span>
                    <span className="text-[10px] text-slate-500 font-mono">{p.model}</span>
                  </div>
                  <p className="text-xs text-slate-500 mb-2">{p.client_name} · {format(parseISO(p.created_at), "dd/MM/yyyy HH:mm")}</p>
                  <pre className="text-xs text-slate-300 whitespace-pre-wrap font-sans bg-[#0E0E11] border border-slate-800 rounded-lg p-3 max-h-52 overflow-y-auto">{p.preview}</pre>
                  {p.status === "aprovado" && p.result && (
                    <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1.5" data-testid={`proposal-result-${p.id}`}>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      {p.result.created_pieces != null ? `${p.result.created_pieces} peça(s) criada(s)`
                        : p.result.created_campaigns != null ? `${p.result.created_campaigns} campanha(s) criada(s)`
                        : p.result.email_id ? `E-mail enviado para ${p.result.to}` : "Executado"}
                    </p>
                  )}
                </div>
                <div className="flex flex-col gap-2 shrink-0 w-32">
                  {p.status === "pendente" ? (
                    <>
                      <Button size="sm" onClick={() => approve(p.id)} disabled={busyId === p.id} className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid={`proposal-approve-${p.id}`}>
                        {busyId === p.id ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Check className="w-3.5 h-3.5 mr-1" />} Aprovar
                      </Button>
                      <Button size="sm" variant="outline" onClick={() => reject(p.id)} className="border-slate-700 bg-white/5 hover:bg-white/10 text-slate-300" data-testid={`proposal-reject-${p.id}`}>
                        <X className="w-3.5 h-3.5 mr-1" /> Rejeitar
                      </Button>
                    </>
                  ) : (
                    <Button size="sm" variant="outline" onClick={() => remove(p.id)} title="Excluir proposta" aria-label="Excluir proposta" className="border-slate-700 bg-white/5 hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 hover:border-rose-500/30" data-testid={`proposal-delete-${p.id}`}>
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={!!active} onOpenChange={(o) => { if (!o) setActive(null); }}>
        <DialogContent className="bg-[#15151A] border-slate-800 text-slate-100" data-testid="agent-run-dialog">
          <DialogHeader><DialogTitle className="font-display">{active?.label}</DialogTitle></DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-slate-300">Cliente *</Label>
              <Select value={form.client_id} onValueChange={(v) => setForm({ ...form, client_id: v })}>
                <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="agent-run-client"><SelectValue placeholder="Selecione" /></SelectTrigger>
                <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200 max-h-64">
                  {clients.map((c) => (<SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-slate-300">Modelo de IA</Label>
                <Select value={form.model} onValueChange={(v) => setForm({ ...form, model: v })}>
                  <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="agent-run-model"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                    {MODELS.map((m) => (<SelectItem key={m.id} value={m.id}>{m.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              {(active?.key === "social" || active?.key === "inbound") && (
                <div className="space-y-2">
                  <Label className="text-slate-300">Quantidade</Label>
                  <Input type="number" min="1" max="10" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: parseInt(e.target.value) || 1 })}
                    className="bg-[#0E0E11] border-slate-700" data-testid="agent-run-quantity" />
                </div>
              )}
            </div>
            <div className="space-y-2">
              <Label className="text-slate-300">Instruções (opcional)</Label>
              <Textarea value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })}
                className="bg-[#0E0E11] border-slate-700 min-h-24" placeholder="Ex.: foco em promoção de dia das mães, tom alegre..." data-testid="agent-run-instructions" />
            </div>
            <Button onClick={run} disabled={running} className="w-full bg-red-600 hover:bg-red-500 text-white" data-testid="agent-run-submit">
              {running ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Gerando proposta...</> : <><Play className="w-4 h-4 mr-2" /> Gerar proposta</>}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
