import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Layers, Trash2, Sparkles, CheckCircle2, Send, CalendarClock } from "lucide-react";
import { toast } from "sonner";
import { format, parseISO } from "date-fns";

const TYPE_LABELS = {
  post_instagram: "Post Instagram", stories: "Stories", anuncio_meta: "Anúncio Meta",
  anuncio_linkedin: "Anúncio LinkedIn", email_marketing: "E-mail", blog: "Blog",
};
const STATUS_LABELS = { rascunho: "Rascunho", aprovada: "Aprovada", agendada: "Agendada", publicada: "Publicada" };
const STATUS_STYLES = {
  rascunho: "bg-slate-500/10 text-slate-400 border-slate-500/20",
  aprovada: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  agendada: "bg-violet-500/10 text-violet-300 border-violet-500/20",
  publicada: "bg-red-500/10 text-red-400 border-red-500/20",
};
const MODEL_BADGES = {
  "gpt-5.4-mini": "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  "claude-sonnet-4-6": "bg-amber-500/10 text-amber-400 border-amber-500/20",
};

export default function Pieces() {
  const navigate = useNavigate();
  const [pieces, setPieces] = useState([]);
  const [clients, setClients] = useState([]);
  const [filterClient, setFilterClient] = useState("all");
  const [expanded, setExpanded] = useState(null);
  const [scheduleTarget, setScheduleTarget] = useState(null);
  const [scheduleAt, setScheduleAt] = useState("");
  const minDateTime = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 16);

  const load = () => {
    api.get("/pieces").then(({ data }) => setPieces(data)).catch(() => {});
    api.get("/clients").then(({ data }) => setClients(data)).catch(() => {});
  };
  useEffect(() => { load(); }, []);

  const clientName = (id) => clients.find((c) => c.id === id)?.name || "Geral";

  const remove = async (id) => {
    try {
      await api.delete(`/pieces/${id}`);
      toast.success("Peça removida");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const approve = async (id) => {
    try {
      await api.put(`/pieces/${id}`, { status: "aprovada" });
      toast.success("Peça aprovada!");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const publishNow = async (id) => {
    try {
      await api.post(`/pieces/${id}/publish`, {});
      toast.success("Peça publicada!");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const doSchedule = async () => {
    if (!scheduleAt) { toast.error("Escolha data e hora"); return; }
    try {
      await api.post(`/pieces/${scheduleTarget}/publish`, { scheduled_at: new Date(scheduleAt).toISOString() });
      toast.success("Peça agendada!");
      setScheduleTarget(null); setScheduleAt("");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const filtered = filterClient === "all" ? pieces : pieces.filter((p) => p.client_id === filterClient);

  return (
    <div className="space-y-6 animate-fade-up" data-testid="pieces-page">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display font-extrabold tracking-tight text-3xl">Peças</h1>
          <p className="text-sm text-slate-400 mt-1">Biblioteca de conteúdo gerado com IA</p>
        </div>
        <div className="flex gap-3">
          <Select value={filterClient} onValueChange={setFilterClient}>
            <SelectTrigger className="bg-[#0E0E11] border-slate-700 w-48" data-testid="pieces-filter-client">
              <SelectValue placeholder="Todos os clientes" />
            </SelectTrigger>
            <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
              <SelectItem value="all">Todos os clientes</SelectItem>
              {clients.map((c) => (
                <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button onClick={() => navigate("/gerar")} className="bg-red-600 hover:bg-red-500 text-white rounded-full" data-testid="new-piece-button">
            <Sparkles className="w-4 h-4 mr-2" /> Nova peça
          </Button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="glass-card p-12 text-center" data-testid="pieces-empty">
          <Layers className="w-10 h-10 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400 mb-4">Nenhuma peça ainda. Gere a primeira com IA.</p>
          <Button onClick={() => navigate("/gerar")} className="bg-red-600 hover:bg-red-500 text-white rounded-full" data-testid="empty-generate-button">
            <Sparkles className="w-4 h-4 mr-2" /> Gerar peça
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((p) => (
            <div key={p.id} className="glass-card p-5 transition-all duration-200 hover:border-slate-700" data-testid={`piece-card-${p.id}`}>
              <div className="flex items-start gap-4">
                {p.image && (
                  <img src={p.image} alt="" className="w-20 h-20 rounded-lg object-cover border border-slate-800 shrink-0" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <h3 className="font-display font-semibold">{p.title}</h3>
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${STATUS_STYLES[p.status] || STATUS_STYLES.rascunho}`}>
                      {STATUS_LABELS[p.status] || p.status}
                    </span>
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-mono border ${MODEL_BADGES[p.model] || MODEL_BADGES["gpt-5.4-mini"]}`}>
                      {p.model}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mb-2">
                    {clientName(p.client_id)} · {TYPE_LABELS[p.piece_type] || p.piece_type} · {format(parseISO(p.created_at), "dd/MM/yyyy HH:mm")}
                    {p.status === "publicada" && p.published_at && (
                      <> · <span className="text-red-400">Publicada {format(parseISO(p.published_at), "dd/MM HH:mm")}</span></>
                    )}
                    {p.status === "agendada" && p.scheduled_at && (
                      <> · <span className="text-violet-300">Agendada p/ {format(parseISO(p.scheduled_at), "dd/MM HH:mm")}</span></>
                    )}
                  </p>
                  <p className={`text-sm text-slate-400 whitespace-pre-wrap ${expanded === p.id ? "" : "line-clamp-2"}`}>
                    {p.content}
                  </p>
                  <button onClick={() => setExpanded(expanded === p.id ? null : p.id)}
                    className="text-xs text-red-400 hover:text-red-300 mt-1" data-testid={`piece-expand-${p.id}`}>
                    {expanded === p.id ? "Ver menos" : "Ver peça completa"}
                  </button>
                </div>
                <div className="flex flex-col gap-2 shrink-0 w-32">
                  {p.status === "rascunho" && (
                    <Button size="sm" onClick={() => approve(p.id)}
                      className="bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30" data-testid={`piece-approve-${p.id}`}>
                      <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Aprovar
                    </Button>
                  )}
                  {p.status !== "publicada" && (
                    <Button size="sm" onClick={() => publishNow(p.id)}
                      className="bg-red-600 hover:bg-red-500 text-white" data-testid={`piece-publish-${p.id}`}>
                      <Send className="w-3.5 h-3.5 mr-1" /> Publicar
                    </Button>
                  )}
                  {p.status !== "publicada" && (
                    <Button size="sm" variant="outline" onClick={() => { setScheduleTarget(p.id); setScheduleAt(""); }}
                      className="border-slate-700 bg-white/5 hover:bg-white/10 text-slate-300" data-testid={`piece-schedule-${p.id}`}>
                      <CalendarClock className="w-3.5 h-3.5 mr-1" /> Agendar
                    </Button>
                  )}
                  <Button size="sm" variant="outline" onClick={() => remove(p.id)}
                    className="border-slate-700 bg-white/5 hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 hover:border-rose-500/30" data-testid={`piece-delete-${p.id}`}>
                    <Trash2 className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={!!scheduleTarget} onOpenChange={(o) => { if (!o) { setScheduleTarget(null); setScheduleAt(""); } }}>
        <DialogContent className="bg-[#15151A] border-slate-800 text-slate-100" data-testid="piece-schedule-dialog">
          <DialogHeader>
            <DialogTitle className="font-display">Agendar publicação</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-slate-300">Data e hora</Label>
              <Input type="datetime-local" min={minDateTime} value={scheduleAt} onChange={(e) => setScheduleAt(e.target.value)}
                className="bg-[#0E0E11] border-slate-700" data-testid="piece-schedule-input" />
            </div>
            <Button onClick={doSchedule} className="w-full bg-red-600 hover:bg-red-500 text-white" data-testid="piece-schedule-confirm">
              <CalendarClock className="w-4 h-4 mr-2" /> Agendar peça
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
