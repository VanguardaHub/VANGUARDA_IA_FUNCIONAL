# Vanguarda.IA — Desenho da Arquitetura

> Plataforma SaaS B2B de IA para agências de marketing. Multi-tenant, geração de peças/imagens com IA contextualizada por marca ("Bíblia"/RAG), dashboard de Meta Ads, agentes operacionais autônomos (human-in-the-loop), custeio de IA por peça e assinaturas Stripe.

---

## 1. Visão geral (C4 — Contexto)

```mermaid
graph TB
    subgraph Users["👤 Usuários"]
        Admin["Dono/Admin da Agência"]
        Op["Operador (member)"]
    end

    subgraph Platform["☁️ Vanguarda.IA (Kubernetes / Emergent)"]
        FE["Frontend React 19<br/>(Tailwind + shadcn/ui)"]
        BE["Backend FastAPI<br/>(Motor / async)"]
        DB[("MongoDB")]
        Cron["Emergent CRON<br/>(.emergent/crons.yml)"]
    end

    subgraph External["🔌 Integrações externas"]
        LLM["Emergent Universal Key<br/>(GPT-5.4 Mini / Claude Sonnet 4.6)"]
        IMG["GPT-Image-1<br/>(geração de imagem)"]
        Stripe["Stripe<br/>(assinaturas)"]
        GAuth["Google OAuth<br/>(Emergent-managed)"]
        Nekt["Nekt MCP<br/>(banco de clientes)"]
        Resend["Resend<br/>(e-mail, Emergent-managed)"]
    end

    Admin --> FE
    Op --> FE
    FE -->|HTTPS /api| BE
    BE --> DB
    Cron -->|POST /api/cron/agents-run| BE
    BE --> LLM
    BE --> IMG
    BE --> Stripe
    BE --> GAuth
    BE --> Nekt
    BE --> Resend
```

---

## 2. Containers (C4 — Containers)

```mermaid
graph LR
    subgraph Browser["Navegador"]
        React["React SPA<br/>react-router-dom 7<br/>axios · recharts · framer-motion"]
    end

    subgraph K8s["Cluster Kubernetes (Ingress)"]
        direction TB
        Ingress["Ingress<br/>/api → :8001 · / → :3000"]
        subgraph Backend["FastAPI :8001"]
            Router["api_router (/api)"]
            Auth["Auth JWT + Google"]
            Pieces["Peças / Gerador IA (SSE)"]
            Agents["Agentes Operacionais"]
            Billing["Billing Stripe"]
            NektMod["nekt.py (MCP client)"]
        end
        Front["Frontend :3000<br/>(craco/CRA)"]
    end

    Mongo[("MongoDB<br/>DB_NAME")]

    React -->|REACT_APP_BACKEND_URL| Ingress
    Ingress --> Router
    Ingress --> Front
    Router --> Auth & Pieces & Agents & Billing & NektMod
    Backend --> Mongo
```

---

## 3. Fluxo — Geração de peça com IA (SSE + custeio)

```mermaid
sequenceDiagram
    participant U as Usuário (Generator.jsx)
    participant BE as FastAPI
    participant RAG as build_brand_context (Bíblia)
    participant LLM as Universal Key (texto)
    participant DB as MongoDB

    U->>BE: POST /api/pieces/generate (gen_group_id, client_id, modelo, tom)
    BE->>RAG: monta contexto de marca (docs Bíblia + Nekt)
    RAG-->>BE: contexto pt-BR
    BE->>LLM: LlmChat streaming (system + prompt)
    loop stream SSE
        LLM-->>BE: tokens
        BE-->>U: data: {delta}
    end
    LLM-->>BE: StreamDone.usage (tokens)
    BE->>DB: record_cost(ai_costs, stage=copy, cost_brl)
    BE-->>U: data: {done, stage, cost_brl, tokens}
    U->>BE: POST /api/pieces (salvar) → vincula ai_costs ao piece_id
```

---

## 4. Fluxo — Geração de imagem assíncrona (fim do 502)

```mermaid
sequenceDiagram
    participant U as Generator.jsx
    participant BE as FastAPI
    participant EXP as expand_image_prompt (texto)
    participant IMG as gpt-image-1 (quality=high)
    participant DB as db.image_jobs

    U->>BE: POST /api/pieces/generate-image (client_id, briefing)
    BE->>DB: cria job {status: processing}
    BE-->>U: {job_id, status} (imediato, sem 502)
    BE->>EXP: expande briefing + Bíblia → prompt art direction (EN)
    EXP-->>BE: prompt rico
    BE->>IMG: gera 1 imagem high
    IMG-->>BE: base64
    BE->>DB: job {status: done, image}
    loop polling 3s
        U->>BE: GET /api/pieces/image-job/{job_id}
        BE-->>U: {status, image?}
    end
    Note over DB: job deletado ao done/error (evita bloat base64)
```

---

## 5. Fluxo — Agentes Operacionais (human-in-the-loop + CRON)

```mermaid
sequenceDiagram
    participant Cron as Emergent CRON (horário)
    participant BE as FastAPI
    participant SCH as db.agent_schedules
    participant LLM as Universal Key
    participant PROP as db.agent_proposals
    participant U as Usuário (Agents.jsx)

    Cron->>BE: POST /api/cron/agents-run (Bearer WEBHOOK_CRON_SECRET)
    BE-->>Cron: 2xx (ack imediato)
    BE->>SCH: _run_due_schedules (idempotência last_run_key)
    BE->>LLM: _agent_generate (plano estruturado JSON)
    LLM-->>BE: proposta (estratégia + datas + custos + brief arte)
    BE->>PROP: salva {status: pendente}

    U->>BE: GET /api/agents/proposals
    U->>BE: PUT /api/agents/proposals/{id} (editar payload)
    U->>BE: POST .../approve  → _apply_proposal
    alt social/inbound
        BE->>BE: cria pieces (rascunho/agendado scheduled_at)
    else midia_paga
        BE->>BE: cria campaigns (budget/datas/brief)
    else account
        BE->>BE: envia e-mail (Resend)
    else otimizacao
        BE->>BE: pausa/ativa/ajusta budget das campanhas
    end
```

---

## 6. Modelo de dados (MongoDB)

```mermaid
erDiagram
    users ||--o{ clients : "owns (user_id)"
    users ||--o{ pieces : "user_id"
    users ||--o{ campaigns : "user_id"
    users ||--o{ bible_documents : "user_id"
    users ||--o{ agent_proposals : "user_id"
    users ||--o{ agent_schedules : "user_id"
    users ||--o{ ai_costs : "user_id"
    clients ||--o{ pieces : "client_id"
    clients ||--o{ campaigns : "client_id"
    clients ||--o{ bible_documents : "client_id"
    pieces ||--o{ ai_costs : "piece_id"
    agent_proposals ||--o{ pieces : "aplica"
    agent_proposals ||--o{ campaigns : "aplica"

    users {
        string id
        string email
        string role "admin|member"
        string plan
        int token_version
    }
    clients {
        string id
        string name
        string cnpj
        string segment
        string source "manual|nekt"
        string nekt_id
    }
    pieces {
        string id
        string status "rascunho|aprovada|publicada|agendada"
        string content
        string image
        string scheduled_at
        float cost_brl
        float billable_brl
    }
    campaigns {
        string id
        string status "ativa|pausada|agendada"
        float budget_daily
        object metrics
    }
    ai_costs {
        string id
        string gen_group_id
        string stage "copy|imagem|refacao|agente"
        string model
        float cost_usd
        float cost_brl
    }
    agent_proposals {
        string id
        string agent_key
        string status "pendente|aprovado|rejeitado"
        object payload
    }
    agent_schedules {
        string id
        string agent_key
        string frequency "daily|weekly"
        int hour
        bool active
    }
```

Demais coleções: `activity_logs`, `alert_rules`, `alert_occurrences`, `app_settings`, `image_jobs`, `login_attempts`, `password_reset_requests`, `password_reset_tokens`, `user_sessions`.

---

## 7. Decisões de arquitetura (ADR resumido)

| # | Decisão | Motivo |
|---|---------|--------|
| 1 | **Universal Key (Emergent)** para LLM em vez de SDKs diretas | Troca de modelo (GPT/Claude) sem gerenciar múltiplas chaves |
| 2 | **Geração de imagem assíncrona** com polling | Evita timeout 502 do proxy de ingress (~55s/imagem) |
| 3 | **Human-in-the-loop** nos agentes (proposta → aprovação → ação) | Controle da agência antes de publicar/pausar/gastar |
| 4 | **CRON da plataforma** (`.emergent/crons.yml`) | Agendamento gerenciado; endpoint só faz ack + background |
| 5 | **Multi-tenant por `user_id`** (sem tabela de tenant) | Simplicidade; todas as queries filtram por `user_id` |
| 6 | **Custeio de IA por etapa** com markup configurável | Agência fatura o cliente com margem sobre o custo real |
| 7 | **Nekt via MCP (JSON-RPC)** read-only | Sincroniza ~133 clientes sem acesso direto ao banco deles |

---

## 8. Observações / dívida técnica

- `backend/server.py` está com ~2160 linhas — recomendado quebrar em `routers/` (auth, pieces, agents, billing, integrations).
- Meta Ads é **mock** (dashboard e ações de otimização atualizam só o estado no DB, não a Graph API real).
- Imagens são armazenadas como **base64** no documento — backlog: mover para object storage (URL).
- RAG da Bíblia usa **sobreposição de palavras**, não embeddings vetoriais.
