import { useEffect, useState } from "react";
import { api, formatApiError, formatBRLPrecise } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Bot, Share2, Magnet, Target, Mail, Loader2, Check, X, Trash2, Play, Clock, CheckCircle2, TrendingUp, Plus, Power, CalendarClock, CheckSquare, Pencil } from "lucide-react";
import { toast } from "sonner";
import { format, parseISO } from "date-fns";

const ICONS = { social: Share2, inbound: Magnet, midia_paga: Target, account: Mail, otimizacao: TrendingUp };
const WEEKDAYS = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"];
const MODELS = [
  { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
  { id: "gpt-5.4-mini", label: "GPT-5.4 Mini" },
];
// Campos editáveis de cada plano. type: text | textarea | number | date | list (separado por vírgula)
const EDIT_SCHEMA = {
  midia_paga: {
    listKey: "campaigns", itemLabel: "Campanha",
    top: [{ key: "estrategia", label: "Estratégia", type: "textarea" }],
    item: [
      { key: "name", label: "Nome da campanha", type: "text", full: true },
      { key: "objetivo_funil", label: "Etapa do funil", type: "text" },
      { key: "objective", label: "Objetivo", type: "text" },
      { key: "budget_daily", label: "Orçamento diário (R$)", type: "number" },
      { key: "duracao_dias", label: "Duração (dias)", type: "number" },
      { key: "data_inicio", label: "Início", type: "date" },
      { key: "data_fim", label: "Fim", type: "date" },
      { key: "kpi_alvo", label: "Meta", type: "text", full: true },
      { key: "audience", label: "Público", type: "textarea" },
      { key: "brief_criativo", label: "Criativo", type: "textarea" },
      { key: "angles", label: "Ângulos criativos (separados por vírgula)", type: "list" },
      { key: "resultado_esperado", label: "Resultado esperado", type: "textarea" },
    ],
  },
  social: {
    listKey: "posts", itemLabel: "Post",
    top: [
      { key: "estrategia", label: "Estratégia", type: "textarea" },
      { key: "periodo", label: "Período", type: "text" },
      { key: "kpis", label: "KPIs (separados por vírgula)", type: "list" },
    ],
    item: [
      { key: "titulo", label: "Título", type: "text", full: true },
      { key: "data_publicacao", label: "Publicação", type: "date" },
      { key: "prazo_arte", label: "Prazo da arte", type: "date" },
      { key: "formato", label: "Formato", type: "text" },
      { key: "pilar", label: "Pilar", type: "text" },
      { key: "tendencia", label: "Tendência", type: "text" },
      { key: "custo_estimado", label: "Custo estimado (R$)", type: "number" },
      { key: "legenda", label: "Legenda", type: "textarea" },
      { key: "hashtags", label: "Hashtags (separadas por vírgula)", type: "list" },
      { key: "cta", label: "CTA", type: "text", full: true },
      { key: "brief_arte", label: "Brief de arte", type: "textarea" },
    ],
  },
  inbound: {
    listKey: "articles", itemLabel: "Artigo",
    top: [
      { key: "estrategia", label: "Estratégia", type: "textarea" },
      { key: "kpis", label: "KPIs (separados por vírgula)", type: "list" },
    ],
    item: [
      { key: "titulo", label: "Título", type: "text", full: true },
      { key: "etapa_funil", label: "Etapa do funil", type: "text" },
      { key: "intencao_busca", label: "Intenção de busca", type: "text" },
      { key: "palavra_chave", label: "Palavra-chave", type: "text" },
      { key: "custo_estimado", label: "Custo estimado (R$)", type: "number" },
      { key: "data_publicacao", label: "Publicação", type: "date" },
      { key: "prazo_redacao", label: "Prazo de redação", type: "date" },
      { key: "keywords", label: "Palavras secundárias (separadas por vírgula)", type: "list" },
      { key: "outline", label: "Estrutura (H2/H3)", type: "textarea" },
      { key: "cta", label: "CTA", type: "text", full: true },
      { key: "brief_arte", label: "Brief da capa", type: "textarea" },
    ],
  },
  account: {
    listKey: null,
    top: [
      { key: "to_email", label: "Para (e-mail)", type: "text" },
      { key: "subject", label: "Assunto", type: "text" },
      { key: "report_text", label: "Relatório", type: "textarea", tall: true },
    ],
    item: [],
  },
};
const PLAN_AGENTS = ["social", "inbound", "midia_paga"];
const canEdit = (p) => !!EDIT_SCHEMA[p.agent_key] && (p.status === "pendente" || (p.status === "aprovado" && PLAN_AGENTS.includes(p.agent_key)));
const toForm = (fields, src) => Object.fromEntries(fields.map((f) => {
  const v = src?.[f.key];
  return [f.key, f.type === "list" ? (Array.isArray(v) ? v.join(", ") : v || "") : v ?? ""];
}));

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
  const [selected, setSelected] = useState([]);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [schedules, setSchedules] = useState([]);
  const [schedOpen, setSchedOpen] = useState(false);
  const [sched, setSched] = useState({ agent_key: "social", client_id: "", model: "claude-sonnet-4-6", instructions: "", quantity: 5, frequency: "weekly", weekday: 1, hour: 9 });

  const [editProp, setEditProp] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [savingEdit, setSavingEdit] = useState(false);

  const openEdit = (p) => {
    const sc = EDIT_SCHEMA[p.agent_key];
    const payload = p.payload || {};
    setEditProp(p);
    setEditForm({
      top: toForm(sc.top, payload),
      items: sc.listKey ? (payload[sc.listKey] || []).map((it) => toForm(sc.item, it)) : [],
    });
  };
  const setTop = (key, value) => setEditForm((f) => ({ ...f, top: { ...f.top, [key]: value } }));
  const setItem = (i, key, value) => setEditForm((f) => ({ ...f, items: f.items.map((it, j) => (j === i ? { ...it, [key]: value } : it)) }));
  const removeItem = (i) => setEditForm((f) => ({ ...f, items: f.items.filter((_, j) => j !== i) }));
  const addItem = () => setEditForm((f) => ({ ...f, items: [...f.items, toForm(EDIT_SCHEMA[editProp.agent_key].item, {})] }));
  const saveEdit = async () => {
    const sc = EDIT_SCHEMA[editProp.agent_key];
    if (sc.listKey && editForm.items.length === 0) { toast.error(`Mantenha ao menos um item (${sc.itemLabel.toLowerCase()})`); return; }
    const payload = { ...editForm.top };
    if (sc.listKey) payload[sc.listKey] = editForm.items;
    setSavingEdit(true);
    try {
      const { data } = await api.put(`/agents/proposals/${editProp.id}`, { payload });
      setProposals((prev) => prev.map((x) => (x.id === data.id ? data : x)));
      toast.success("Plano atualizado");
      setEditProp(null);
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSavingEdit(false);
    }
  };

  const renderField = (f, value, onChange, testId) => (
    <div key={f.key} className={`space-y-1.5 ${f.full || f.type === "textarea" || f.type === "list" ? "col-span-2" : ""}`}>
      <Label className="text-slate-300 text-xs">{f.label}</Label>
      {f.type === "textarea" ? (
        <Textarea value={value} onChange={(e) => onChange(e.target.value)} className={`bg-[#0E0E11] border-slate-700 text-sm ${f.tall ? "min-h-[240px]" : "min-h-20"}`} data-testid={testId} />
      ) : (
        <Input type={f.type === "number" ? "number" : f.type === "date" ? "date" : "text"} min={f.type === "number" ? "0" : undefined}
          value={value} onChange={(e) => onChange(e.target.value)} className="bg-[#0E0E11] border-slate-700" data-testid={testId} />
      )}
    </div>
  );

  const loadScheds = () => api.get("/agents/schedules").then(({ data }) => setSchedules(data)).catch(() => {});

  const loadProps = () => api.get("/agents/proposals").then(({ data }) => setProposals(data)).catch(() => {});
  useEffect(() => {
    api.get("/agents").then(({ data }) => setAgents(data)).catch(() => {});
    api.get("/clients").then(({ data }) => setClients(data)).catch(() => {});
    loadProps();
    loadScheds();
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

  const toggleSel = (id) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  const bulkApprove = async () => {
    setBulkBusy(true);
    try {
      const { data } = await api.post("/agents/proposals/bulk", { ids: selected, action: "approve" });
      toast.success(`${data.approved} aprovada(s)${data.errors ? `, ${data.errors} falha(s)` : ""}`);
      setSelected([]); loadProps();
    } catch (err) { toast.error(formatApiError(err)); } finally { setBulkBusy(false); }
  };
  const bulkReject = async () => {
    setBulkBusy(true);
    try {
      const { data } = await api.post("/agents/proposals/bulk", { ids: selected, action: "reject" });
      toast.success(`${data.rejected} rejeitada(s)`);
      setSelected([]); loadProps();
    } catch (err) { toast.error(formatApiError(err)); } finally { setBulkBusy(false); }
  };

  const createSched = async () => {
    if (!sched.client_id) { toast.error("Selecione um cliente"); return; }
    try { await api.post("/agents/schedules", sched); toast.success("Agendamento criado"); setSchedOpen(false); loadScheds(); }
    catch (err) { toast.error(formatApiError(err)); }
  };
  const toggleSched = async (s) => {
    try { await api.patch(`/agents/schedules/${s.id}`, { active: !s.active }); loadScheds(); }
    catch (err) { toast.error(formatApiError(err)); }
  };
  const delSched = async (id) => {
    try { await api.delete(`/agents/schedules/${id}`); loadScheds(); }
    catch (err) { toast.error(formatApiError(err)); }
  };

  const pending = proposals.filter((p) => p.status === "pendente");
  const allPendingSelected = pending.length > 0 && selected.length >= pending.length;
  const toggleSelectAll = () => setSelected(allPendingSelected ? [] : pending.map((p) => p.id));

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

      {pending.length > 0 && (
        <div className="flex items-center gap-3 flex-wrap glass-card p-3" data-testid="bulk-bar">
          <button onClick={toggleSelectAll} className="text-xs text-slate-300 flex items-center gap-1.5 hover:text-white" data-testid="bulk-select-all">
            <CheckSquare className="w-4 h-4" /> {allPendingSelected ? "Limpar seleção" : "Selecionar pendentes"}
          </button>
          <span className="text-xs text-slate-500">{selected.length} selecionada(s)</span>
          {selected.length > 0 && (
            <div className="flex gap-2 ml-auto">
              <Button size="sm" onClick={bulkApprove} disabled={bulkBusy} className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="bulk-approve">
                {bulkBusy ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <Check className="w-3.5 h-3.5 mr-1" />} Aprovar selecionadas
              </Button>
              <Button size="sm" variant="outline" onClick={bulkReject} disabled={bulkBusy} className="border-slate-700 bg-white/5 hover:bg-white/10 text-slate-300" data-testid="bulk-reject">
                <X className="w-3.5 h-3.5 mr-1" /> Rejeitar
              </Button>
            </div>
          )}
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="glass-card p-12 text-center text-slate-500 text-sm" data-testid="proposals-empty">
          Nenhuma proposta {filter !== "all" ? filter : "ainda"}. Rode um agente acima para começar.
        </div>
      ) : (
        <div className="space-y-3" data-testid="proposals-list">
          {filtered.map((p) => (
            <div key={p.id} className="glass-card p-5" data-testid={`proposal-${p.id}`}>
              <div className="flex items-start gap-4">
                {p.status === "pendente" && (
                  <input type="checkbox" checked={selected.includes(p.id)} onChange={() => toggleSel(p.id)}
                    className="mt-1.5 w-4 h-4 accent-red-500 shrink-0" data-testid={`proposal-select-${p.id}`} />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <h3 className="font-display font-semibold">{p.title}</h3>
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border capitalize ${STATUS[p.status]}`} data-testid={`proposal-status-${p.id}`}>{p.status}</span>
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-mono border bg-white/5 border-slate-700 text-slate-400">{p.agent_label}</span>
                    <span className="text-[10px] text-slate-500 font-mono">{p.model}</span>
                  </div>
                  <p className="text-xs text-slate-500 mb-2">
                    {p.client_name} · {format(parseISO(p.created_at), "dd/MM/yyyy HH:mm")}
                    {p.edited_at && <> · <span className="text-slate-400">Editado {format(parseISO(p.edited_at), "dd/MM HH:mm")}</span></>}
                  </p>
                  <pre className="text-xs text-slate-300 whitespace-pre-wrap font-sans bg-[#0E0E11] border border-slate-800 rounded-lg p-3 max-h-80 overflow-y-auto">{p.preview}</pre>
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
                  {canEdit(p) && (
                    <Button size="sm" variant="outline" onClick={() => openEdit(p)} className="border-slate-700 bg-white/5 hover:bg-white/10 text-slate-200" data-testid={`proposal-edit-${p.id}`}>
                      <Pencil className="w-3.5 h-3.5 mr-1" /> Editar
                    </Button>
                  )}
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

      <div className="flex items-center justify-between flex-wrap gap-3 pt-2">
        <h2 className="font-display font-bold text-xl flex items-center gap-2"><CalendarClock className="w-5 h-5 text-red-400" /> Agendamentos</h2>
        <Button size="sm" onClick={() => { setSched({ agent_key: "social", client_id: clients[0]?.id || "", model: "claude-sonnet-4-6", instructions: "", quantity: 5, frequency: "weekly", weekday: 1, hour: 9 }); setSchedOpen(true); }} className="bg-red-600 hover:bg-red-500 text-white rounded-full" data-testid="schedule-new">
          <Plus className="w-3.5 h-3.5 mr-1.5" /> Novo agendamento
        </Button>
      </div>
      {schedules.length === 0 ? (
        <div className="glass-card p-6 text-center text-slate-500 text-sm" data-testid="schedules-empty">Nenhum agendamento. Programe um agente para rodar sozinho e cair na fila de aprovação.</div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-3" data-testid="schedules-list">
          {schedules.map((s) => (
            <div key={s.id} className="glass-card p-4 flex items-center gap-3" data-testid={`schedule-${s.id}`}>
              <div className="flex-1 min-w-0">
                <p className="font-medium text-sm truncate">{s.agent_label} · {s.client_name}</p>
                <p className="text-xs text-slate-500">{s.frequency === "daily" ? "Diário" : `Semanal (${WEEKDAYS[s.weekday]})`} às {String(s.hour).padStart(2, "0")}:00 UTC · {s.model}{s.active ? "" : " · pausado"}</p>
              </div>
              <button onClick={() => toggleSched(s)} title={s.active ? "Pausar" : "Ativar"} aria-label={s.active ? "Pausar" : "Ativar"} className={`p-2 rounded-lg hover:bg-white/5 ${s.active ? "text-emerald-400" : "text-slate-500"}`} data-testid={`schedule-toggle-${s.id}`}><Power className="w-4 h-4" /></button>
              <button onClick={() => delSched(s.id)} title="Remover agendamento" aria-label="Remover agendamento" className="p-2 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10" data-testid={`schedule-delete-${s.id}`}><Trash2 className="w-4 h-4" /></button>
            </div>
          ))}
        </div>
      )}

      <Dialog open={!!active} onOpenChange={(o) => { if (!o) setActive(null); }}>
        <DialogContent className="bg-[#15151A] border-slate-800 text-slate-100" data-testid="agent-run-dialog">
          <DialogHeader><DialogTitle className="font-display">{active?.label}</DialogTitle>
            <DialogDescription className="text-slate-400">Gere uma proposta para revisão — nada é executado sem sua aprovação.</DialogDescription>
          </DialogHeader>
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

      <Dialog open={!!editProp} onOpenChange={(o) => { if (!o && !savingEdit) setEditProp(null); }}>
        <DialogContent className="bg-[#15151A] border-slate-800 text-slate-100 max-w-3xl max-h-[90vh] overflow-y-auto" data-testid="proposal-edit-dialog">
          {editProp && editForm && (() => {
            const sc = EDIT_SCHEMA[editProp.agent_key];
            return (
              <>
                <DialogHeader>
                  <DialogTitle className="font-display pr-8">Editar — {editProp.title}</DialogTitle>
                  <DialogDescription className="text-slate-400">
                    {editProp.status === "pendente"
                      ? "As alterações valem para o que será criado quando você aprovar."
                      : "Este plano já foi aprovado: a edição atualiza apenas o registro do plano. As campanhas/peças já criadas não são alteradas."}
                  </DialogDescription>
                </DialogHeader>
                <div className="grid grid-cols-2 gap-3">
                  {sc.top.map((f) => renderField(f, editForm.top[f.key], (v) => setTop(f.key, v), `edit-top-${f.key}`))}
                </div>
                {sc.listKey && (
                  <div className="space-y-3 pt-2">
                    {editForm.items.map((it, i) => (
                      <div key={i} className="rounded-lg border border-slate-800 bg-white/[0.02] p-4" data-testid={`edit-item-${i}`}>
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-xs uppercase tracking-wider text-slate-500">{sc.itemLabel} {i + 1}</span>
                          <button onClick={() => removeItem(i)} title={`Remover ${sc.itemLabel.toLowerCase()}`} aria-label={`Remover ${sc.itemLabel.toLowerCase()}`}
                            className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10" data-testid={`edit-item-remove-${i}`}>
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          {sc.item.map((f) => renderField(f, it[f.key], (v) => setItem(i, f.key, v), `edit-item-${i}-${f.key}`))}
                        </div>
                      </div>
                    ))}
                    {editForm.items.length < 10 && (
                      <Button variant="outline" size="sm" onClick={addItem} className="border-slate-700 bg-white/5 hover:bg-white/10 text-slate-300" data-testid="edit-item-add">
                        <Plus className="w-3.5 h-3.5 mr-1.5" /> Adicionar {sc.itemLabel.toLowerCase()}
                      </Button>
                    )}
                  </div>
                )}
                <div className="flex gap-2 pt-4 border-t border-slate-800">
                  <Button onClick={saveEdit} disabled={savingEdit} className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="edit-save">
                    {savingEdit ? <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Salvando...</> : "Salvar alterações"}
                  </Button>
                  <Button variant="outline" onClick={() => setEditProp(null)} disabled={savingEdit} className="border-slate-700 bg-white/5 text-slate-300" data-testid="edit-cancel">Cancelar</Button>
                </div>
              </>
            );
          })()}
        </DialogContent>
      </Dialog>

      <Dialog open={schedOpen} onOpenChange={setSchedOpen}>
        <DialogContent className="bg-[#15151A] border-slate-800 text-slate-100" data-testid="schedule-dialog">
          <DialogHeader><DialogTitle className="font-display">Novo agendamento</DialogTitle>
            <DialogDescription className="text-slate-400">O agente roda no horário definido e a proposta cai na fila para você aprovar.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-slate-300">Agente</Label>
                <Select value={sched.agent_key} onValueChange={(v) => setSched({ ...sched, agent_key: v })}>
                  <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="schedule-agent"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                    {agents.map((a) => (<SelectItem key={a.key} value={a.key}>{a.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-slate-300">Cliente</Label>
                <Select value={sched.client_id} onValueChange={(v) => setSched({ ...sched, client_id: v })}>
                  <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="schedule-client"><SelectValue placeholder="Selecione" /></SelectTrigger>
                  <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200 max-h-64">
                    {clients.map((c) => (<SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-slate-300">Modelo</Label>
                <Select value={sched.model} onValueChange={(v) => setSched({ ...sched, model: v })}>
                  <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="schedule-model"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                    {MODELS.map((m) => (<SelectItem key={m.id} value={m.id}>{m.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-slate-300">Frequência</Label>
                <Select value={sched.frequency} onValueChange={(v) => setSched({ ...sched, frequency: v })}>
                  <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="schedule-frequency"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                    <SelectItem value="daily">Diário</SelectItem>
                    <SelectItem value="weekly">Semanal</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {sched.frequency === "weekly" && (
                <div className="space-y-2">
                  <Label className="text-slate-300">Dia da semana</Label>
                  <Select value={String(sched.weekday)} onValueChange={(v) => setSched({ ...sched, weekday: parseInt(v) })}>
                    <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="schedule-weekday"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                      {WEEKDAYS.map((d, i) => (<SelectItem key={i} value={String(i)}>{d}</SelectItem>))}
                    </SelectContent>
                  </Select>
                </div>
              )}
              <div className="space-y-2">
                <Label className="text-slate-300">Hora (UTC)</Label>
                <Input type="number" min="0" max="23" value={sched.hour} onChange={(e) => setSched({ ...sched, hour: parseInt(e.target.value) || 0 })} className="bg-[#0E0E11] border-slate-700" data-testid="schedule-hour" />
              </div>
              {(sched.agent_key === "social" || sched.agent_key === "inbound") && (
                <div className="space-y-2">
                  <Label className="text-slate-300">Quantidade</Label>
                  <Input type="number" min="1" max="10" value={sched.quantity} onChange={(e) => setSched({ ...sched, quantity: parseInt(e.target.value) || 1 })} className="bg-[#0E0E11] border-slate-700" data-testid="schedule-quantity" />
                </div>
              )}
            </div>
            <div className="space-y-2">
              <Label className="text-slate-300">Instruções (opcional)</Label>
              <Textarea value={sched.instructions} onChange={(e) => setSched({ ...sched, instructions: e.target.value })} className="bg-[#0E0E11] border-slate-700 min-h-20" data-testid="schedule-instructions" />
            </div>
            <p className="text-xs text-slate-500">O agente roda no horário definido e a proposta cai na fila para você aprovar. Horário em UTC.</p>
            <Button onClick={createSched} className="w-full bg-red-600 hover:bg-red-500 text-white" data-testid="schedule-submit">
              <CalendarClock className="w-4 h-4 mr-2" /> Criar agendamento
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
