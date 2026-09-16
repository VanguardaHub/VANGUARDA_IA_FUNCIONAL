import { useEffect, useRef, useState } from "react";
import { api, streamSSE, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { BookOpen, Plus, Trash2, Send, Loader2, FileText } from "lucide-react";
import { toast } from "sonner";
import { format, parseISO } from "date-fns";

const CATEGORIES = ["Geral", "Brand Persona", "Guidelines", "Playbook", "Produto", "Concorrentes"];

export default function Bible() {
  const [docs, setDocs] = useState([]);
  const [form, setForm] = useState({ title: "", category: "Geral", content: "" });
  const [saving, setSaving] = useState(false);
  const [question, setQuestion] = useState("");
  const [model, setModel] = useState("gpt-5.4-mini");
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState([]);
  const answerRef = useRef(null);

  const load = () => api.get("/bible/documents").then(({ data }) => setDocs(data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const addDoc = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      await api.post("/bible/documents", form);
      toast.success("Documento adicionado à Bíblia");
      setForm({ title: "", category: "Geral", content: "" });
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const removeDoc = async (id) => {
    try {
      await api.delete(`/bible/documents/${id}`);
      toast.success("Documento removido");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  const ask = async () => {
    if (!question.trim()) return;
    setAsking(true);
    setAnswer("");
    setSources([]);
    let full = "";
    await streamSSE("/bible/ask", { question, model }, {
      onMeta: (m) => setSources(m.sources || []),
      onDelta: (d) => {
        full += d;
        setAnswer(full);
      },
      onDone: () => setAsking(false),
      onError: (e) => {
        setAsking(false);
        toast.error(e);
      },
    });
  };

  useEffect(() => {
    answerRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [answer]);

  return (
    <div className="space-y-6 animate-fade-up" data-testid="bible-page">
      <div>
        <h1 className="font-display font-extrabold tracking-tight text-3xl">Bíblia</h1>
        <p className="text-sm text-slate-400 mt-1">Base de conhecimento da agência — a IA usa estes documentos como contexto</p>
      </div>

      <Tabs defaultValue="ask" className="space-y-5">
        <TabsList className="bg-[#15151A] border border-slate-800" data-testid="bible-tabs">
          <TabsTrigger value="ask" data-testid="bible-tab-ask">Consulta com IA</TabsTrigger>
          <TabsTrigger value="docs" data-testid="bible-tab-docs">Documentos ({docs.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="ask">
          <div className="glass-card p-5 sm:p-6 space-y-5" data-testid="bible-ask-panel">
            <div className="flex gap-3 flex-wrap">
              <div className="flex-1 min-w-[240px]">
                <Input
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && !asking && ask()}
                  className="bg-[#0E0E11] border-slate-700 h-11"
                  placeholder="Ex.: Qual o tom de voz do Café Aroma? Qual o CTR saudável para Meta Ads?"
                  data-testid="bible-question-input"
                />
              </div>
              <Select value={model} onValueChange={setModel}>
                <SelectTrigger className="bg-[#0E0E11] border-slate-700 w-52" data-testid="bible-model-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                  <SelectItem value="gpt-5.4-mini" data-testid="bible-model-gpt">GPT-5.4 Mini</SelectItem>
                  <SelectItem value="claude-sonnet-4-6" data-testid="bible-model-claude">Claude Sonnet 4.6</SelectItem>
                </SelectContent>
              </Select>
              <Button onClick={ask} disabled={asking} className="bg-red-600 hover:bg-red-500 text-white h-11" data-testid="bible-ask-button">
                {asking ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
              </Button>
            </div>

            {(answer || asking) && (
              <div className="space-y-4" ref={answerRef}>
                {sources.length > 0 && (
                  <div className="flex gap-2 flex-wrap" data-testid="bible-sources">
                    {sources.map((s) => (
                      <span key={s.id} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs">
                        <FileText className="w-3 h-3" /> {s.title}
                      </span>
                    ))}
                  </div>
                )}
                <div className={`whitespace-pre-wrap text-sm leading-relaxed text-slate-200 bg-[#0E0E11] border border-slate-800 rounded-xl p-5 ${asking ? "streaming-cursor" : ""}`} data-testid="bible-answer">
                  {answer || "Consultando a Bíblia..."}
                </div>
              </div>
            )}

            {!answer && !asking && (
              <div className="text-center py-12">
                <BookOpen className="w-10 h-10 text-slate-600 mx-auto mb-3" />
                <p className="text-sm text-slate-500 max-w-md mx-auto">
                  Pergunte qualquer coisa sobre as marcas, playbooks e guidelines cadastrados. A IA responde citando as fontes da Bíblia.
                </p>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="docs">
          <div className="grid lg:grid-cols-3 gap-4 md:gap-6">
            <div className="glass-card p-5 h-fit" data-testid="bible-add-doc">
              <h3 className="font-display font-semibold text-lg mb-4">Novo documento</h3>
              <form onSubmit={addDoc} className="space-y-4">
                <div className="space-y-2">
                  <Label className="text-slate-300">Título *</Label>
                  <Input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                    className="bg-[#0E0E11] border-slate-700" placeholder="Guia de Tom de Voz — Cliente X" data-testid="bible-doc-title" />
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Categoria</Label>
                  <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                    <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="bible-doc-category">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                      {CATEGORIES.map((c) => (
                        <SelectItem key={c} value={c}>{c}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Conteúdo *</Label>
                  <Textarea required value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })}
                    className="bg-[#0E0E11] border-slate-700 min-h-40" placeholder="Cole aqui o guia, persona, playbook ou guideline..." data-testid="bible-doc-content" />
                </div>
                <Button type="submit" disabled={saving} className="w-full bg-red-600 hover:bg-red-500 text-white" data-testid="bible-doc-submit">
                  {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
                  Adicionar à Bíblia
                </Button>
              </form>
            </div>

            <div className="lg:col-span-2 space-y-3">
              {docs.length === 0 ? (
                <div className="glass-card p-12 text-center text-slate-500 text-sm" data-testid="bible-docs-empty">
                  Nenhum documento na Bíblia ainda.
                </div>
              ) : (
                docs.map((d) => (
                  <div key={d.id} className="glass-card p-5 group" data-testid={`bible-doc-${d.id}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <h3 className="font-display font-semibold">{d.title}</h3>
                          <span className="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-rose-500/10 text-rose-300 border border-rose-500/20">
                            {d.category}
                          </span>
                        </div>
                        <p className="text-sm text-slate-400 line-clamp-3 whitespace-pre-wrap">{d.content}</p>
                        <p className="text-xs text-slate-600 font-mono mt-2">{format(parseISO(d.created_at), "dd/MM/yyyy HH:mm")}</p>
                      </div>
                      <button onClick={() => removeDoc(d.id)} data-testid={`bible-doc-delete-${d.id}`}
                        className="opacity-0 group-hover:opacity-100 transition-opacity p-2 rounded-lg hover:bg-rose-500/10 text-slate-500 hover:text-rose-400 shrink-0">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
