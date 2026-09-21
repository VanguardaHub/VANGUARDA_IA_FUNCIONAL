import { useEffect, useState } from "react";
import { api, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Save, Loader2, Cpu, Building2, KeyRound, Users, UserPlus, Pencil, Trash2, Receipt } from "lucide-react";
import { toast } from "sonner";
import { format, parseISO } from "date-fns";

const TONES = ["profissional", "persuasivo", "descontraído", "luxuoso", "motivacional", "urgente"];
const ROLES = [{ id: "member", label: "Membro" }, { id: "admin", label: "Admin" }];
const PLANS = [{ id: "trial", label: "Trial" }, { id: "starter", label: "Starter" }, { id: "pro", label: "Pro" }, { id: "agency", label: "Enterprise" }];
const EMPTY_USER = { name: "", email: "", password: "", role: "member", plan: "trial" };
const planLabel = (id) => PLANS.find((p) => p.id === id)?.label || id;

export default function Settings() {
  const { user } = useAuth();
  const [settings, setSettings] = useState(null);
  const [users, setUsers] = useState([]);
  const [saving, setSaving] = useState(false);
  const [userDialogOpen, setUserDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [userForm, setUserForm] = useState(EMPTY_USER);
  const [savingUser, setSavingUser] = useState(false);

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

  const openCreate = () => {
    setEditingUser(null);
    setUserForm(EMPTY_USER);
    setUserDialogOpen(true);
  };

  const updatePricing = (k, v) =>
    setSettings((s) => ({ ...s, pricing: { ...s.pricing, [k]: v === "" ? "" : parseFloat(v) } }));
  const updateModelPrice = (mid, k, v) =>
    setSettings((s) => ({ ...s, pricing: { ...s.pricing, models: { ...s.pricing.models, [mid]: { ...s.pricing.models[mid], [k]: v === "" ? "" : parseFloat(v) } } } }));
  const savePricing = async () => {
    setSaving(true);
    try {
      await api.put("/settings", { pricing: settings.pricing });
      toast.success("Tabela de custos salva");
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSaving(false);
    }
  };

  const openEdit = (u) => {
    setEditingUser(u);
    setUserForm({ name: u.name, email: u.email, password: "", role: u.role, plan: u.plan });
    setUserDialogOpen(true);
  };

  const submitUser = async (e) => {
    e.preventDefault();
    setSavingUser(true);
    try {
      if (editingUser) {
        const payload = { name: userForm.name, role: userForm.role, plan: userForm.plan };
        if (userForm.password) payload.password = userForm.password;
        await api.put(`/admin/users/${editingUser.user_id}`, payload);
        toast.success("Usuário atualizado");
      } else {
        await api.post("/admin/users", userForm);
        toast.success("Usuário criado");
      }
      setUserDialogOpen(false);
      load();
    } catch (err) {
      toast.error(formatApiError(err));
    } finally {
      setSavingUser(false);
    }
  };

  const deleteUser = async (u) => {
    if (!window.confirm(`Remover a conta de ${u.name} (${u.email})? Esta ação não pode ser desfeita.`)) return;
    try {
      await api.delete(`/admin/users/${u.user_id}`);
      toast.success("Usuário removido");
      load();
    } catch (err) {
      toast.error(formatApiError(err));
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
          {user?.role === "admin" && (
            <TabsTrigger value="pricing" data-testid="settings-tab-pricing"><Receipt className="w-3.5 h-3.5 mr-1.5" /> Custos & Preços</TabsTrigger>
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
            <div className="space-y-4 max-w-3xl">
              <div className="flex items-center justify-between">
                <p className="text-sm text-slate-400">Gerencie as contas de acesso à plataforma. O cadastro público está desativado.</p>
                <Button onClick={openCreate} className="bg-red-600 hover:bg-red-500 text-white rounded-full" data-testid="new-user-button">
                  <UserPlus className="w-4 h-4 mr-2" /> Novo usuário
                </Button>
              </div>
              <div className="glass-card overflow-hidden" data-testid="users-table">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-800 text-left text-xs text-slate-500 uppercase tracking-wider">
                      <th className="p-4">Usuário</th>
                      <th className="p-4">E-mail</th>
                      <th className="p-4">Papel</th>
                      <th className="p-4">Plano</th>
                      <th className="p-4">Desde</th>
                      <th className="p-4 text-right">Ações</th>
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
                        <td className="p-4 font-mono text-xs">{planLabel(u.plan)}</td>
                        <td className="p-4 text-slate-500 text-xs">{u.created_at ? format(parseISO(u.created_at), "dd/MM/yyyy") : "—"}</td>
                        <td className="p-4">
                          <div className="flex items-center justify-end gap-2">
                            <Button size="sm" variant="outline" onClick={() => openEdit(u)}
                              className="border-slate-700 bg-white/5 hover:bg-white/10 text-slate-300" data-testid={`user-edit-${u.user_id}`}>
                              <Pencil className="w-3.5 h-3.5" />
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => deleteUser(u)} disabled={u.user_id === user.user_id}
                              className="border-slate-700 bg-white/5 hover:bg-rose-500/10 text-slate-400 hover:text-rose-400 hover:border-rose-500/30 disabled:opacity-40"
                              data-testid={`user-delete-${u.user_id}`}>
                              <Trash2 className="w-3.5 h-3.5" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </TabsContent>
        )}

        {user?.role === "admin" && (
          <TabsContent value="pricing">
            <div className="glass-card p-6 space-y-6 max-w-2xl" data-testid="pricing-panel">
              <p className="text-sm text-slate-400">
                Tabela editável usada para <strong>estimar</strong> o custo de IA por peça e por etapa. Valores em US$; convertidos para R$ pela taxa abaixo. O faturamento real da chave é em créditos Emergent.
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-slate-300">Taxa US$ → R$</Label>
                  <Input type="number" step="0.01" value={settings.pricing?.usd_to_brl ?? ""} onChange={(e) => updatePricing("usd_to_brl", e.target.value)}
                    className="bg-[#0E0E11] border-slate-700" data-testid="pricing-usd-brl" />
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Markup (%)</Label>
                  <Input type="number" step="1" value={settings.pricing?.markup_pct ?? ""} onChange={(e) => updatePricing("markup_pct", e.target.value)}
                    className="bg-[#0E0E11] border-slate-700" data-testid="pricing-markup" />
                </div>
                <div className="space-y-2 col-span-2">
                  <Label className="text-slate-300">Imagem — US$ por unidade (alta qualidade)</Label>
                  <Input type="number" step="0.01" value={settings.pricing?.image_high_per_unit ?? ""} onChange={(e) => updatePricing("image_high_per_unit", e.target.value)}
                    className="bg-[#0E0E11] border-slate-700" data-testid="pricing-image" />
                </div>
              </div>
              {Object.entries(settings.pricing?.models || {}).map(([mid, mp]) => (
                <div key={mid} className="border-t border-slate-800 pt-4" data-testid={`pricing-model-${mid}`}>
                  <p className="text-sm font-medium mb-2 font-mono text-slate-300">{mid}</p>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label className="text-slate-300">Entrada (US$/1M tokens)</Label>
                      <Input type="number" step="0.01" value={mp.input_per_m ?? ""} onChange={(e) => updateModelPrice(mid, "input_per_m", e.target.value)}
                        className="bg-[#0E0E11] border-slate-700" data-testid={`pricing-${mid}-input`} />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-slate-300">Saída (US$/1M tokens)</Label>
                      <Input type="number" step="0.01" value={mp.output_per_m ?? ""} onChange={(e) => updateModelPrice(mid, "output_per_m", e.target.value)}
                        className="bg-[#0E0E11] border-slate-700" data-testid={`pricing-${mid}-output`} />
                    </div>
                  </div>
                </div>
              ))}
              <Button onClick={savePricing} disabled={saving} className="bg-red-600 hover:bg-red-500 text-white" data-testid="settings-save-pricing">
                {saving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                Salvar tabela de custos
              </Button>
            </div>
          </TabsContent>
        )}
      </Tabs>

      <Dialog open={userDialogOpen} onOpenChange={setUserDialogOpen}>
        <DialogContent className="bg-[#15151A] border-slate-800 text-slate-100" data-testid="user-dialog">
          <DialogHeader>
            <DialogTitle className="font-display">{editingUser ? "Editar usuário" : "Novo usuário"}</DialogTitle>
            <DialogDescription className="text-slate-500 text-sm">
              {editingUser ? "Atualize os dados de acesso desta conta." : "Crie uma nova conta de acesso à plataforma."}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submitUser} className="space-y-4">
            <div className="space-y-2">
              <Label className="text-slate-300">Nome completo *</Label>
              <Input required value={userForm.name} onChange={(e) => setUserForm({ ...userForm, name: e.target.value })}
                className="bg-[#0E0E11] border-slate-700" placeholder="Maria Silva" data-testid="user-form-name" />
            </div>
            <div className="space-y-2">
              <Label className="text-slate-300">E-mail *</Label>
              <Input type="email" required disabled={!!editingUser} value={userForm.email}
                onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                className="bg-[#0E0E11] border-slate-700 disabled:opacity-60" placeholder="pessoa@agencia.com.br" data-testid="user-form-email" />
            </div>
            <div className="space-y-2">
              <Label className="text-slate-300">{editingUser ? "Nova senha (opcional)" : "Senha *"}</Label>
              <Input type="password" required={!editingUser} minLength={6} value={userForm.password}
                onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                className="bg-[#0E0E11] border-slate-700" placeholder={editingUser ? "Deixe em branco para manter" : "Mínimo 6 caracteres"}
                data-testid="user-form-password" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-slate-300">Papel</Label>
                <Select value={userForm.role} onValueChange={(v) => setUserForm({ ...userForm, role: v })}>
                  <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="user-form-role"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                    {ROLES.map((r) => (<SelectItem key={r.id} value={r.id}>{r.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label className="text-slate-300">Plano</Label>
                <Select value={userForm.plan} onValueChange={(v) => setUserForm({ ...userForm, plan: v })}>
                  <SelectTrigger className="bg-[#0E0E11] border-slate-700" data-testid="user-form-plan"><SelectValue /></SelectTrigger>
                  <SelectContent className="bg-[#15151A] border-slate-800 text-slate-200">
                    {PLANS.map((p) => (<SelectItem key={p.id} value={p.id}>{p.label}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button type="submit" disabled={savingUser} className="w-full bg-red-600 hover:bg-red-500 text-white" data-testid="user-form-submit">
              {savingUser ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
              {editingUser ? "Salvar alterações" : "Criar usuário"}
            </Button>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
