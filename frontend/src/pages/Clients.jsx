import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, formatApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Plus, Users, Sparkles, Trash2, ArrowRight } from "lucide-react";
import { toast } from "sonner";

export default function Clients() {
  const navigate = useNavigate();
  const [clients, setClients] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ name: "", segment: "", contact_name: "", contact_email: "", brand_color: "#6366F1", notes: "" });

  const load = () => api.get("/clients").then(({ data }) => setClients(data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/clients", form);
      toast.success("Cliente cadastrado!");
      setOpen(false);
      setForm({ name: "", segment: "", contact_name: "", contact_email: "", brand_color: "#6366F1", notes: "" });
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const remove = async (id, name) => {
    try {
      await api.delete(`/clients/${id}`);
      toast.success(`Cliente "${name}" removido`);
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    }
  };

  return (
    <div className="space-y-6 animate-fade-up" data-testid="clients-page">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="font-display font-extrabold tracking-tight text-3xl">Clientes</h1>
          <p className="text-sm text-slate-400 mt-1">Carteira de clientes da agência</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-full" data-testid="new-client-button">
              <Plus className="w-4 h-4 mr-2" /> Novo cliente
            </Button>
          </DialogTrigger>
          <DialogContent className="bg-[#11131A] border-slate-800 text-slate-100 sm:max-w-lg" data-testid="new-client-dialog">
            <DialogHeader>
              <DialogTitle className="font-display">Cadastrar cliente</DialogTitle>
            </DialogHeader>
            <form onSubmit={submit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2 col-span-2">
                  <Label className="text-slate-300">Nome da marca *</Label>
                  <Input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="bg-[#0C0D13] border-slate-700" placeholder="Café Aroma" data-testid="client-name-input" />
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Segmento</Label>
                  <Input value={form.segment} onChange={(e) => setForm({ ...form, segment: e.target.value })}
                    className="bg-[#0C0D13] border-slate-700" placeholder="Alimentação" data-testid="client-segment-input" />
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Cor da marca</Label>
                  <Input type="color" value={form.brand_color} onChange={(e) => setForm({ ...form, brand_color: e.target.value })}
                    className="bg-[#0C0D13] border-slate-700 h-10 p-1" data-testid="client-color-input" />
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Contato</Label>
                  <Input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
                    className="bg-[#0C0D13] border-slate-700" placeholder="Marina Lopes" data-testid="client-contact-input" />
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">E-mail do contato</Label>
                  <Input type="email" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
                    className="bg-[#0C0D13] border-slate-700" placeholder="contato@marca.com" data-testid="client-email-input" />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label className="text-slate-300">Observações da marca (a IA usa isso como contexto)</Label>
                  <Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })}
                    className="bg-[#0C0D13] border-slate-700 min-h-24" placeholder="Tom de voz, público-alvo, restrições..." data-testid="client-notes-input" />
                </div>
              </div>
              <Button type="submit" disabled={loading} className="w-full bg-indigo-600 hover:bg-indigo-500 text-white" data-testid="client-submit-button">
                {loading ? "Salvando..." : "Cadastrar cliente"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      {clients.length === 0 ? (
        <div className="glass-card p-12 text-center" data-testid="clients-empty">
          <Users className="w-10 h-10 text-slate-600 mx-auto mb-4" />
          <p className="text-slate-400">Nenhum cliente ainda. Cadastre o primeiro para começar.</p>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 md:gap-6">
          {clients.map((c) => (
            <div key={c.id} className="glass-card p-5 transition-all duration-200 hover:-translate-y-0.5 hover:border-slate-700 group" data-testid={`client-card-${c.id}`}>
              <div className="flex items-start justify-between mb-4">
                <div className="w-11 h-11 rounded-xl flex items-center justify-center font-display font-bold text-white text-lg"
                  style={{ background: `linear-gradient(135deg, ${c.brand_color}, ${c.brand_color}88)` }}>
                  {c.name.slice(0, 1)}
                </div>
                <button onClick={() => remove(c.id, c.name)} data-testid={`client-delete-${c.id}`}
                  className="opacity-0 group-hover:opacity-100 transition-opacity p-2 rounded-lg hover:bg-rose-500/10 text-slate-500 hover:text-rose-400">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
              <h3 className="font-display font-semibold text-lg">{c.name}</h3>
              <p className="text-xs text-slate-500">{c.segment || "Segmento não informado"}</p>
              <div className="flex gap-4 mt-4 text-xs text-slate-400">
                <span><strong className="text-slate-200">{c.campaigns_count}</strong> campanhas</span>
                <span><strong className="text-slate-200">{c.pieces_count}</strong> peças</span>
              </div>
              <div className="flex gap-2 mt-5">
                <Button size="sm" variant="outline" onClick={() => navigate(`/clientes/${c.id}`)}
                  className="flex-1 border-slate-700 bg-white/5 hover:bg-white/10 text-slate-200" data-testid={`client-view-${c.id}`}>
                  Detalhes <ArrowRight className="w-3.5 h-3.5 ml-1" />
                </Button>
                <Button size="sm" onClick={() => navigate(`/gerar?cliente=${c.id}`)}
                  className="bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30" data-testid={`client-generate-${c.id}`}>
                  <Sparkles className="w-3.5 h-3.5 mr-1" /> Gerar peça
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
