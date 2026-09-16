import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, formatBRL } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Sparkles, Megaphone, Layers, Mail, User, Tag } from "lucide-react";
import { format, parseISO } from "date-fns";

const STATUS_STYLES = {
  ativa: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  pausada: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  em_analise: "bg-blue-500/10 text-blue-400 border-blue-500/20",
};
const STATUS_LABELS = { ativa: "Ativa", pausada: "Pausada", em_analise: "Em análise" };

export default function ClientDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [client, setClient] = useState(null);

  useEffect(() => {
    api.get(`/clients/${id}`).then(({ data }) => setClient(data)).catch(() => navigate("/clientes"));
  }, [id, navigate]);

  if (!client)
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );

  return (
    <div className="space-y-6 animate-fade-up" data-testid="client-detail-page">
      <Button variant="ghost" onClick={() => navigate("/clientes")} className="text-slate-400 hover:text-white -ml-2" data-testid="back-to-clients">
        <ArrowLeft className="w-4 h-4 mr-2" /> Voltar para clientes
      </Button>

      <div className="glass-card p-6 flex flex-wrap items-center gap-5">
        <div className="w-16 h-16 rounded-2xl flex items-center justify-center font-display font-bold text-white text-2xl"
          style={{ background: `linear-gradient(135deg, ${client.brand_color}, ${client.brand_color}88)` }}>
          {client.name.slice(0, 1)}
        </div>
        <div className="flex-1 min-w-[200px]">
          <h1 className="font-display font-extrabold tracking-tight text-2xl" data-testid="client-detail-name">{client.name}</h1>
          <div className="flex flex-wrap gap-x-5 gap-y-1 mt-2 text-sm text-slate-400">
            <span className="flex items-center gap-1.5"><Tag className="w-3.5 h-3.5" /> {client.segment || "—"}</span>
            <span className="flex items-center gap-1.5"><User className="w-3.5 h-3.5" /> {client.contact_name || "—"}</span>
            <span className="flex items-center gap-1.5"><Mail className="w-3.5 h-3.5" /> {client.contact_email || "—"}</span>
          </div>
        </div>
        <Button onClick={() => navigate(`/gerar?cliente=${client.id}`)} className="bg-red-600 hover:bg-red-500 text-white rounded-full" data-testid="detail-generate-button">
          <Sparkles className="w-4 h-4 mr-2" /> Gerar peça
        </Button>
      </div>

      {client.notes && (
        <div className="glass-card p-5">
          <h3 className="font-display font-semibold text-sm text-slate-400 uppercase tracking-wider mb-2">Contexto da marca (usado pela IA)</h3>
          <p className="text-sm text-slate-300 leading-relaxed">{client.notes}</p>
        </div>
      )}

      <div>
        <h2 className="font-display font-bold text-xl mb-4 flex items-center gap-2"><Megaphone className="w-5 h-5 text-red-400" /> Campanhas</h2>
        {client.campaigns.length === 0 ? (
          <div className="glass-card p-8 text-center text-slate-500 text-sm">Nenhuma campanha vinculada.</div>
        ) : (
          <div className="grid sm:grid-cols-2 gap-4">
            {client.campaigns.map((c) => {
              const spend = (c.metrics || []).reduce((s, m) => s + m.spend, 0);
              return (
                <div key={c.id} className="glass-card p-5" data-testid={`detail-campaign-${c.id}`}>
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-display font-semibold">{c.name}</h3>
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-semibold border ${STATUS_STYLES[c.status]}`}>
                      {STATUS_LABELS[c.status]}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 font-mono">{c.ad_account_id}</p>
                  <p className="text-sm text-slate-300 mt-3">{formatBRL(spend)} investidos</p>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div>
        <h2 className="font-display font-bold text-xl mb-4 flex items-center gap-2"><Layers className="w-5 h-5 text-fuchsia-400" /> Peças recentes</h2>
        {client.pieces.length === 0 ? (
          <div className="glass-card p-8 text-center text-slate-500 text-sm">Nenhuma peça gerada para este cliente.</div>
        ) : (
          <div className="space-y-3">
            {client.pieces.slice(0, 8).map((p) => (
              <div key={p.id} className="glass-card p-4 flex items-center gap-4" data-testid={`detail-piece-${p.id}`}>
                <div className="flex-1 min-w-0">
                  <h4 className="font-medium text-sm truncate">{p.title}</h4>
                  <p className="text-xs text-slate-500">{format(parseISO(p.created_at), "dd/MM/yyyy HH:mm")}</p>
                </div>
                <span className="text-xs px-2 py-1 rounded-md bg-white/5 border border-slate-700 text-slate-400 font-mono">{p.model}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
