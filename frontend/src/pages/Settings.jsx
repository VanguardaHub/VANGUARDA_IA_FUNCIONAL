import { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Save, Loader2, Cpu, Building2, KeyRound, Users } from "lucide-react";
import { toast } from "sonner";
import { format, parseISO } from "date-fns";

const TONES = ["profissional", "persuasivo", "descontraído", "luxuoso", "motivacional", "urgente"];

export default function Settings() {
  const { user } = useAuth();
  const [settings, setSettings] = useState(null);
  const [users, setUsers] = useState([]);
  const [saving, setSaving] = useState(false);

  const load = () => {
    api.get("/settings").then(({ data }) => setSettings(data)).catch(() => {});
    if (user?.role === "admin") {
      api.get("/admin/users").then(({ data }) => setUsers(data)).catch(() => {});
    }
  };
  useEffect(() => { load(); }, [user]);

  const save = async () => {
    setSaving(true);
    try {
      await api.put("/settings", {
        default_model: settings.default_model,
        default_tone: settings.default_tone,
        agency_name: settings.agency_name,
        meta_connected: settings.meta_connected,
      });
      toast.success("Configurações salvas");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  if (!settings)
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );

  return (
    <div className="space-y-6 animate-fade-up" data-testid="settings-page">
      <div>
        <h1 className="font-display font-extrabold tracking-tight text-3xl">Configurações</h1>
        <p className="text-sm text-slate-400 mt-1">Modelos de IA, integrações e preferências da agência</p>
      </div>

      <Tabs defaultValue="models" className="space-y-5">
        <TabsList className="bg-[#15151A] border border-slate-800" data-testid="settings-tabs">
          <TabsTrigger value="models" data-testid="settings-tab-models"><Cpu className="w-3.5 h-3.5 mr-1.5" /> Modelos de IA</TabsTrigger>
          <TabsTrigger value="agency" data-testid="settings-tab-agency"><Building2 className="w-3.5 h-3.5 mr-1.5" /> Agência</TabsTrigger>
          <TabsTrigger value="integrations" data-testid="settings-tab-integrations"><KeyRound className="w-3.5 h-3.5 mr-1.5" /> Integrações</TabsTrigger>
          {user?.role === "admin" && (
            <TabsTrigger value="team" data-testid="settings-tab-team"><Users className="w-3.5 h-3.5 mr-1.5" /> Usuários</TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="models">
          <div className="glass-card p-6 space-y-6 max-w-2xl">
            <div className="space-y-2">
              <Label className="text-slate-300">Modelo padrão de geração</Label>
              <div className="grid sm:grid-cols-2 gap-3">
                {(settings.available_models || []).map((m) => (
                  <button key={m.id} type="button"
                    onClick={() => setSettings({ ...settings, default_model: m.id })}
                    data-testid={`default-model-${m.id}`}
                    className={`p-4 rounded-lg border text-left transition-all ${
                      settings.default_model === m.id
                        ? "border-red-500/50 bg-red-500/10"
                        : "border-slate-800 bg-white/[0.02] hover:border-slate-700"
                    }`}>
                    <p className="text-sm font-medium">{m.label}</p>
                    <p className="text-xs text-slate-500 font-mono mt-1">{m.id}</p>
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-2">
              <Label className="text-slate-300">Tom de voz padrão</Label>
              <Select value={settings.default_tone} onValueChange={(v) => setSettings({ ...settings, default_tone: v })}>
                <SelectTrigger className="bg-[#0E0E11] border-slate-700 capitalize" data-testid="default-tone-select">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                  {TONES.map((t) => (
                    <SelectItem key={t} value={t} className="capitalize">{t}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Button onClick={save} disabled={saving} className="bg-red-600 hover:bg-red-500 text-white" data-testid="settings-save-models">
              {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              Salvar preferências
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="agency">
          <div className="glass-card p-6 space-y-6 max-w-2xl">
            <div className="space-y-2">
              <Label className="text-slate-300">Nome da agência</Label>
              <Input value={settings.agency_name || ""} onChange={(e) => setSettings({ ...settings, agency_name: e.target.value })}
                className="bg-[#0E0E11] border-slate-700" placeholder="Vanguarda Digital" data-testid="agency-name-input" />
            </div>
            <Button onClick={save} disabled={saving} className="bg-red-600 hover:bg-red-500 text-white" data-testid="settings-save-agency">
              {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              Salvar
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="integrations">
          <div className="glass-card p-6 space-y-5 max-w-2xl">
            <div className="flex items-center justify-between p-4 rounded-lg border border-slate-800 bg-white/[0.02]" data-testid="meta-integration">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center">
                  <span className="text-blue-400 font-bold text-sm font-mono">f</span>
                </div>
                <div>
                  <p className="text-sm font-medium">Meta Ads</p>
                  <p className="text-xs text-slate-500">Piloto — sincronização de campanhas e métricas</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs font-medium ${settings.meta_connected ? "text-emerald-400" : "text-slate-500"}`} data-testid="meta-status">
                  {settings.meta_connected ? "Conectado" : "Desconectado"}
                </span>
                <Switch
                  checked={!!settings.meta_connected}
                  onCheckedChange={(v) => setSettings({ ...settings, meta_connected: v })}
                  data-testid="meta-toggle"
                />
              </div>
            </div>
            <div className="flex items-center justify-between p-4 rounded-lg border border-slate-800 bg-white/[0.02]">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                  <Cpu className="w-5 h-5 text-emerald-400" />
                </div>
                <div>
                  <p className="text-sm font-medium">Provedores de IA</p>
                  <p className="text-xs text-slate-500">OpenAI + Anthropic via chave universal</p>
                </div>
              </div>
              <span className="text-xs font-medium text-emerald-400" data-testid="ai-status">Ativo</span>
            </div>
            <Button onClick={save} disabled={saving} className="bg-red-600 hover:bg-red-500 text-white" data-testid="settings-save-integrations">
              {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              Salvar integrações
            </Button>
          </div>
        </TabsContent>

        {user?.role === "admin" && (
          <TabsContent value="team">
            <div className="glass-card overflow-hidden max-w-3xl" data-testid="users-table">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-left text-xs text-slate-500 uppercase tracking-wider">
                    <th className="p-4">Usuário</th>
                    <th className="p-4">E-mail</th>
                    <th className="p-4">Papel</th>
                    <th className="p-4">Plano</th>
                    <th className="p-4">Desde</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.user_id} className="border-b border-slate-800/50 hover:bg-white/[0.02]" data-testid={`user-row-${u.user_id}`}>
                      <td className="p-4 font-medium">{u.name}</td>
                      <td className="p-4 text-slate-400">{u.email}</td>
                      <td className="p-4">
                        <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${
                          u.role === "admin" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" : "bg-slate-500/10 text-slate-400 border-slate-500/20"
                        }`}>
                          {u.role === "admin" ? "Admin" : "Membro"}
                        </span>
                      </td>
                      <td className="p-4 font-mono text-xs">{u.plan}</td>
                      <td className="p-4 text-slate-500 text-xs">{u.created_at ? format(parseISO(u.created_at), "dd/MM/yyyy") : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}
