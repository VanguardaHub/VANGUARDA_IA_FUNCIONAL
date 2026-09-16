import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { api, streamSSE, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Sparkles, Image as ImageIcon, Save, Loader2, Instagram, Linkedin, Mail, FileText, Megaphone, Smartphone } from "lucide-react";
import { toast } from "sonner";

const PIECE_TYPES = [
  { id: "post_instagram", label: "Post Instagram", icon: Instagram },
  { id: "stories", label: "Stories", icon: Smartphone },
  { id: "anuncio_meta", label: "Anúncio Meta Ads", icon: Megaphone },
  { id: "anuncio_linkedin", label: "Anúncio LinkedIn", icon: Linkedin },
  { id: "email_marketing", label: "E-mail marketing", icon: Mail },
  { id: "blog", label: "Artigo de blog", icon: FileText },
];

const MODELS = [
  { id: "gpt-5.4-mini", label: "GPT-5.4 Mini", desc: "Rápido e eficiente", badge: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20" },
  { id: "claude-sonnet-4-6", label: "Claude Sonnet 4.6", desc: "Redação criativa premium", badge: "bg-amber-500/10 text-amber-400 border-amber-500/20" },
];

const TONES = ["profissional", "persuasivo", "descontraído", "luxuoso", "motivacional", "urgente"];

export default function Generator() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [clients, setClients] = useState([]);
  const [form, setForm] = useState({
    client_id: params.get("cliente") || "",
    piece_type: "post_instagram",
    model: "gpt-5.4-mini",
    tone: "profissional",
    prompt: "",
  });
  const [withImage, setWithImage] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [generatingImage, setGeneratingImage] = useState(false);
  const [content, setContent] = useState("");
  const [image, setImage] = useState(null);
  const [saving, setSaving] = useState(false);
  const [title, setTitle] = useState("");

  useEffect(() => {
    api.get("/clients").then(({ data }) => setClients(data)).catch(() => {});
    api.get("/settings").then(({ data }) => {
      if (data.default_model) setForm((f) => ({ ...f, model: data.default_model }));
      if (data.default_tone) setForm((f) => ({ ...f, tone: data.default_tone }));
    }).catch(() => {});
  }, []);

  const generate = async () => {
    if (!form.prompt.trim()) {
      toast.error("Descreva o briefing da peça");
      return;
    }
    setGenerating(true);
    setContent("");
    setTitle("");
    let full = "";
    await streamSSE("/pieces/generate", { ...form, client_id: form.client_id || null }, {
      onDelta: (d) => {
        full += d;
        setContent(full);
        const m = full.match(/TÍTULO:\s*(.+)/i);
        if (m) setTitle(m[1].trim());
      },
      onDone: () => {
        setGenerating(false);
        toast.success("Peça gerada com sucesso!");
      },
      onError: (e) => {
        setGenerating(false);
        toast.error(e);
      },
    });
  };

  const generateImage = async () => {
    if (!form.prompt.trim()) {
      toast.error("Descreva o briefing antes de gerar a imagem");
      return;
    }
    setGeneratingImage(true);
    try {
      const { data } = await api.post("/pieces/generate-image", {
        prompt: `${form.prompt}. Marca: ${clients.find((c) => c.id === form.client_id)?.name || "genérica"}. Formato: ${PIECE_TYPES.find((t) => t.id === form.piece_type)?.label}.`,
      });
      setImage(data.image);
      toast.success("Imagem gerada!");
    } catch (err) {
      toast.error(formatApiError(err, "Falha ao gerar imagem"));
    } finally {
      setGeneratingImage(false);
    }
  };

  const save = async () => {
    if (!content.trim()) return;
    setSaving(true);
    try {
      await api.post("/pieces", {
        client_id: form.client_id || null,
        title: title || `Peça — ${PIECE_TYPES.find((t) => t.id === form.piece_type)?.label}`,
        piece_type: form.piece_type,
        model: form.model,
        prompt: form.prompt,
        content,
        image,
        status: "rascunho",
      });
      toast.success("Peça salva na biblioteca!");
      navigate("/pecas");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="animate-fade-up" data-testid="generator-page">
      <div className="mb-6">
        <h1 className="font-display font-extrabold tracking-tight text-3xl">Gerar Peça</h1>
        <p className="text-sm text-slate-400 mt-1">Motor criativo com IA — do briefing à peça pronta</p>
      </div>

      <div className="grid lg:grid-cols-5 gap-4 md:gap-6">
        <div className="lg:col-span-2 space-y-5">
          <div className="glass-card p-5 space-y-5">
            <div className="space-y-2">
              <Label className="text-slate-300">Cliente</Label>
              <Select value={form.client_id} onValueChange={(v) => setForm({ ...form, client_id: v })}>
                <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="generator-client-select">
                  <SelectValue placeholder="Selecione o cliente" />
                </SelectTrigger>
                <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                  {clients.map((c) => (
                    <SelectItem key={c.id} value={c.id} data-testid={`generator-client-option-${c.id}`}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-slate-300">Formato da peça</Label>
              <div className="grid grid-cols-2 gap-2">
                {PIECE_TYPES.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setForm({ ...form, piece_type: t.id })}
                    data-testid={`piece-type-${t.id}`}
                    className={`flex items-center gap-2 p-2.5 rounded-lg border text-xs font-medium transition-all ${
                      form.piece_type === t.id
                        ? "border-red-500/50 bg-red-500/10 text-red-300"
                        : "border-slate-800 bg-white/[0.02] text-slate-400 hover:border-slate-700"
                    }`}
                  >
                    <t.icon className="w-3.5 h-3.5" /> {t.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-slate-300">Modelo de IA</Label>
              <div className="space-y-2">
                {MODELS.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => setForm({ ...form, model: m.id })}
                    data-testid={`model-option-${m.id}`}
                    className={`w-full flex items-center justify-between p-3 rounded-lg border text-left transition-all ${
                      form.model === m.id
                        ? "border-red-500/50 bg-red-500/10"
                        : "border-slate-800 bg-white/[0.02] hover:border-slate-700"
                    }`}
                  >
                    <div>
                      <p className="text-sm font-medium">{m.label}</p>
                      <p className="text-xs text-slate-500">{m.desc}</p>
                    </div>
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-mono border ${m.badge}`}>{m.id}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-slate-300">Tom de voz</Label>
              <Select value={form.tone} onValueChange={(v) => setForm({ ...form, tone: v })}>
                <SelectTrigger className="bg-[#0E0E11] border-slate-700 capitalize" data-testid="generator-tone-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                  {TONES.map((t) => (
                    <SelectItem key={t} value={t} className="capitalize" data-testid={`tone-option-${t}`}>{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-slate-300">Briefing</Label>
              <Textarea
                value={form.prompt}
                onChange={(e) => setForm({ ...form, prompt: e.target.value })}
                className="bg-[#0E0E11] border-slate-700 min-h-28"
                placeholder="Ex.: Lançamento do novo blend de inverno do Café Aroma, foco em edição limitada e experiência sensorial..."
                data-testid="generator-prompt-input"
              />
            </div>

            <div className="flex items-center justify-between py-1">
              <Label className="text-slate-300 flex items-center gap-2">
                <ImageIcon className="w-4 h-4 text-red-400" /> Gerar imagem com IA
              </Label>
              <Switch checked={withImage} onCheckedChange={setWithImage} data-testid="generator-image-toggle" />
            </div>

            <Button
              onClick={generate}
              disabled={generating}
              className="w-full bg-red-600 hover:bg-red-500 text-white h-11"
              data-testid="generate-piece-submit-button"
            >
              {generating ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Gerando com {MODELS.find((m) => m.id === form.model)?.label}...</>
              ) : (
                <><Sparkles className="w-4 h-4 mr-2" /> Gerar peça com IA</>
              )}
            </Button>
          </div>
        </div>

        <div className="lg:col-span-3">
          <div className="glass-card p-5 sm:p-6 min-h-[500px] flex flex-col" data-testid="generator-preview">
            <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
              <h3 className="font-display font-semibold text-lg">Preview</h3>
              <div className="flex gap-2">
                {withImage && content && !image && (
                  <Button size="sm" variant="outline" onClick={generateImage} disabled={generatingImage}
                    className="border-slate-700 bg-white/5 hover:bg-white/10 text-slate-200" data-testid="generate-image-button">
                    {generatingImage ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <ImageIcon className="w-3.5 h-3.5 mr-1.5" />}
                    {generatingImage ? "Gerando imagem..." : "Gerar imagem"}
                  </Button>
                )}
                {content && (
                  <Button size="sm" onClick={save} disabled={saving}
                    className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="save-piece-button">
                    {saving ? <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <Save className="w-3.5 h-3.5 mr-1.5" />}
                    Salvar peça
                  </Button>
                )}
              </div>
            </div>

            {!content && !generating ? (
              <div className="flex-1 flex flex-col items-center justify-center text-center py-16">
                <div className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/20 flex items-center justify-center mb-4">
                  <Sparkles className="w-6 h-6 text-red-400" />
                </div>
                <p className="text-slate-400 text-sm max-w-xs">
                  Configure os parâmetros ao lado, descreva o briefing e clique em <strong>Gerar peça com IA</strong>.
                </p>
              </div>
            ) : (
              <div className="flex-1 space-y-5">
                {image && (
                  <div className="rounded-xl overflow-hidden border border-slate-800" data-testid="generated-image-preview">
                    <img src={image} alt="Criativo gerado por IA" className="w-full max-h-80 object-cover" />
                  </div>
                )}
                {generatingImage && (
                  <div className="rounded-xl border border-slate-800 bg-white/[0.02] h-48 flex items-center justify-center">
                    <Loader2 className="w-6 h-6 animate-spin text-red-400" />
                  </div>
                )}
                <div
                  className={`whitespace-pre-wrap text-sm leading-relaxed text-slate-200 bg-[#0E0E11] border border-slate-800 rounded-xl p-5 ${generating ? "streaming-cursor" : ""}`}
                  data-testid="generated-content"
                >
                  {content || "Aguardando o modelo..."}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
