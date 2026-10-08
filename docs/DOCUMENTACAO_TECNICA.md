# Vanguarda.IA — Documentação Técnica

Plataforma SaaS B2B de IA para agências de marketing. Este documento descreve stack, estrutura, configuração, endpoints da API, modelo de dados, integrações e operação.

> Diagramas de arquitetura: ver [`ARQUITETURA.md`](./ARQUITETURA.md).

---

## 1. Stack tecnológica

### Frontend
- **React 19** + **react-router-dom 7**
- **Tailwind CSS 3** + **shadcn/ui** (Radix UI)
- **Recharts** (gráficos), **framer-motion** (animações)
- **axios** (HTTP), **sonner** (toasts), **@react-oauth/google**
- Build: **craco** (CRA). Idioma: **pt-BR**. Tema: dark "obsidian" + vermelho Vanguarda (`#FF2D40`).

### Backend
- **FastAPI 0.110** + **Uvicorn**
- **Motor** (MongoDB async)
- **PyJWT** (JWT em cookie httpOnly) + **bcrypt**
- **emergentintegrations** (`LlmChat` streaming SSE, `OpenAIImageGeneration`)
- **resend** (e-mail), **Model Context Protocol** via `nekt.py` (JSON-RPC 2.0 sobre HTTP Streamable)

### Infra
- Kubernetes (Emergent preview). Backend `0.0.0.0:8001`, Frontend `:3000`, ambos via Supervisor.
- Ingress: rotas `/api/*` → backend; demais → frontend.
- CRON gerenciado pela plataforma (`.emergent/crons.yml`).

---

## 2. Estrutura do projeto

```
/app/
├── backend/
│   ├── server.py          # Aplicação FastAPI principal (~2160 linhas)
│   ├── nekt.py            # Cliente Nekt MCP (JSON-RPC)
│   ├── payments.py        # Catálogo de planos + lógica Stripe
│   ├── setup_stripe.py    # Bootstrap de produtos/preços no Stripe
│   ├── requirements.txt
│   ├── Procfile / runtime.txt   # deploy externo
│   └── tests/             # pytest (ex.: test_ai_costs.py)
├── frontend/
│   └── src/
│       ├── App.js         # Rotas (ProtectedRoute, AppLayout)
│       ├── lib/api.js     # cliente axios + helpers (formatBRL)
│       ├── pages/         # Landing, Dashboard, Clients, Generator,
│       │                  # Pieces, Bible, Campaigns, Logs, Settings,
│       │                  # Reports(custos), Agents, Plans, auth/*
│       └── components/ui/ # shadcn
├── docs/                  # esta documentação
├── memory/                # PRD.md, test_credentials.md
├── .emergent/crons.yml    # agendamento de agentes
└── test_reports/          # relatórios do testing agent
```

---

## 3. Configuração (variáveis de ambiente)

### backend/.env
| Chave | Descrição |
|-------|-----------|
| `MONGO_URL`, `DB_NAME` | Conexão MongoDB (não alterar) |
| `JWT_SECRET` | Assinatura dos tokens JWT |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Admin semeado; login com `ADMIN_EMAIL` é auto-promovido a admin/agency |
| `EMERGENT_LLM_KEY` | Universal Key (GPT/Claude/gpt-image-1) |
| `EMERGENT_EMAIL_KEY`, `EMAIL_FROM_NAME` | Envio de e-mail (Resend gerenciado) |
| `NEKT_MCP_URL`, `NEKT_MCP_TOKEN` | Integração Nekt MCP |
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_MODE`, `STRIPE_ACCOUNT_ID` | Stripe |
| `WEBHOOK_CRON_SECRET` | Bearer validado em `/api/cron/agents-run` |
| `CORS_ORIGINS`, `FRONTEND_URL` | CORS / redirects |

### frontend/.env
| Chave | Descrição |
|-------|-----------|
| `REACT_APP_BACKEND_URL` | URL externa do backend (todas as chamadas) |
| `REACT_APP_GOOGLE_CLIENT_ID` | (opcional) Google OAuth próprio em deploy externo |

> Nunca commitar `.env`. Chamadas de frontend sempre via `REACT_APP_BACKEND_URL`; rotas de backend sempre com prefixo `/api`.

---

## 4. Autenticação

- **JWT e-mail/senha**: `bcrypt` para hash; token em cookie httpOnly; `token_version` invalida sessões ao resetar senha.
- **Google OAuth**: no preview usa fluxo Emergent-managed; em deploy externo (com `GOOGLE_CLIENT_ID`) verifica `id_token` via `google-auth`.
- **Auto-promoção**: `ensure_owner_admin()` promove qualquer login do `ADMIN_EMAIL` a `admin`/`agency` (evita "base vazia").
- **Reset de senha**: e-mail real via proxy Emergent; tokens em `password_reset_tokens`.
- Proteção contra brute force: `login_attempts`.

---

## 5. API — endpoints (prefixo `/api`)

### Auth
| Método | Rota |
|--------|------|
| POST | `/auth/register`, `/auth/login`, `/auth/logout`, `/auth/refresh` |
| GET | `/auth/me` |
| POST | `/auth/forgot-password`, `/auth/reset-password`, `/auth/google/session` |

### Clientes
| Método | Rota |
|--------|------|
| GET | `/clients`, `/clients/{id}` |
| POST | `/clients` |
| PUT/DELETE | `/clients/{id}` |

### Peças / Gerador IA
| Método | Rota |
|--------|------|
| GET | `/pieces`, `/pieces/image-job/{job_id}` |
| POST | `/pieces`, `/pieces/generate` (SSE), `/pieces/generate-image` (async), `/pieces/{id}/publish` |
| PUT/DELETE | `/pieces/{id}` |

### Bíblia (RAG)
| Método | Rota |
|--------|------|
| GET | `/bible/documents` |
| POST | `/bible/documents`, `/bible/upload` (PDF/DOCX/XLSX/img/txt), `/bible/ask` |
| DELETE | `/bible/documents/{id}` |

### Campanhas (Meta Ads — mock)
| Método | Rota |
|--------|------|
| GET | `/campaigns`, `/campaigns/{id}/metrics` |
| POST | `/campaigns`, `/campaigns/{id}/publish`, `/campaigns/{id}/status`, `/campaigns/{id}/sync` |

### Agentes Operacionais
| Método | Rota |
|--------|------|
| GET | `/agents`, `/agents/proposals`, `/agents/schedules` |
| POST | `/agents/{agent_key}/run`, `/agents/proposals/bulk`, `/agents/proposals/{id}/approve`, `/agents/proposals/{id}/reject`, `/agents/schedules` |
| PUT/PATCH | `/agents/proposals/{id}`, `/agents/schedules/{id}` |
| DELETE | `/agents/proposals/{id}`, `/agents/schedules/{id}` |
| POST | `/cron/agents-run` (webhook CRON, Bearer `WEBHOOK_CRON_SECRET`) |

### Custos / Relatórios / Logs / Config / Admin / Integrações
| Método | Rota |
|--------|------|
| GET | `/dashboard`, `/reports/costs`, `/logs`, `/settings`, `/admin/users` |
| POST | `/alerts/rules`, `/admin/users`, `/integrations/nekt/test`, `/integrations/nekt/sync-clients` |
| GET | `/alerts/rules`, `/integrations/nekt/status` |
| PUT | `/settings`, `/admin/users/{id}` |
| DELETE | `/alerts/rules/{id}`, `/admin/users/{id}` |

---

## 6. Agentes Operacionais

Cinco agentes (registry `AGENTS`), cada execução escolhe o modelo (Claude Sonnet 4.6 ou GPT-5.4 Mini):

| Agente | `agent_key` | Saída | Ação ao aprovar |
|--------|-------------|-------|-----------------|
| Social Media | `social` | Cronograma com datas, pilares, roteiro de reels/stories, legenda, hashtags, CTA, brief de arte, horário (fuso Brasília) | Cria `pieces` (agendadas em `scheduled_at`) |
| Inbound | `inbound` | Artigos por etapa de funil, keywords, outline, CTA, brief | Cria `pieces` rascunho |
| Mídia Paga | `midia_paga` | Campanhas com objetivo, budget, datas, audience, angles, KPI | Cria `campaigns` |
| Account | `account` | E-mail de relacionamento/relatório ao cliente | Envia e-mail (Resend) |
| Otimização | `otimizacao` | Lê métricas 14d e recomenda pausar/ativar/escalar/reduzir | Ajusta status/`budget_daily` das campanhas |

Fluxo: `run` (ou CRON) → gera **proposta** (`agent_proposals`, status `pendente`) → usuário edita (`PUT`) / aprova em lote (`bulk`) → `_apply_proposal` executa. Cada execução grava custo em `ai_costs` (stage `agente`).

Agendamento: `agent_schedules` (daily/weekly, hour UTC, idempotência `last_run_key`). CRON horário (`.emergent/crons.yml`) chama `/api/cron/agents-run` que faz ack imediato e dispara `_run_due_schedules` em background.

---

## 7. Custeio de IA

- `DEFAULT_PRICING`: `usd_to_brl=5.40`, `markup_pct=100`, preços por modelo (ex.: gpt-5.4-mini 0.15/0.60; claude-sonnet-4-6 3.0/15.0 US$/1M tokens) e imagem high ~0.19 US$.
- Helpers: `get_pricing`, `_text_cost_usd`, `record_cost`, `stage_for`.
- Etapas: `copy`, `refacao_texto`, `imagem`, `refacao_imagem`, `agente`.
- Exibição: painel em tempo real no Generator, chip + bloco por etapa nas Peças, KPIs no Dashboard (`kpi-ai-cost`, `kpi-ai-billable`) e página **/custos** (`Reports.jsx`) com totais, margem e tabela por cliente.
- Tabela de preços e markup editáveis em **Configurações → Custos & Preços** (admin).

---

## 8. Integrações externas

| Integração | Uso | Chave |
|------------|-----|-------|
| OpenAI GPT-5.4 Mini | Texto de peças e agentes | Universal Key |
| Anthropic Claude Sonnet 4.6 | Texto de agentes (default) | Universal Key |
| gpt-image-1 | Geração de imagem | Universal Key |
| Stripe | Assinaturas (Starter R$97, Pro R$197, Enterprise R$397/mês; anual −20%) | Chave do usuário |
| Google OAuth | Login social | Emergent-managed (preview) |
| Nekt MCP | Sync de ~133 clientes (view `..._vw_cliente_entidade_vbot`) | Token do usuário |
| Resend | E-mail do Account Agent e reset de senha | Emergent-managed |

---

## 9. Execução e operação

- **Serviços**: gerenciados pelo Supervisor. `sudo supervisorctl restart backend|frontend` só após mudar `.env` ou instalar dependências (hot reload cobre o resto).
- **Logs backend**: `/var/log/supervisor/backend.*.log`.
- **Testes**: `pytest` no backend (ex.: `tests/test_ai_costs.py`, 9/9); E2E por testing agent (relatórios em `/app/test_reports/`).
- **Deploy externo**: `DEPLOY.md` (MongoDB Atlas + backend Procfile/runtime + Vercel + Google OAuth próprio); `render.yaml`, `frontend/vercel.json`.
- **Credenciais de teste**: `memory/test_credentials.md` (admin `jussaracavalcante25@gmail.com`).

---

## 10. Dívida técnica / backlog

- Quebrar `server.py` em `routers/` (auth, pieces, agents, billing, integrations).
- Meta Ads real (Graph API) — hoje é mock.
- Imagens em object storage (hoje base64 no documento).
- RAG vetorial (embeddings) para a Bíblia.
- UI de edição de proposta antes de aprovar (em andamento); seletor de horário em fuso Brasília; notificação diária de propostas pendentes.
