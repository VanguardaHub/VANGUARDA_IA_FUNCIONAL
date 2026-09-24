# PRD — Vanguarda.IA

## Problema original
"crie este sistema de acordo com o documento ele será um saas vendável no mercado" — Documento: Mapa de Transferência Técnica do Vanguarda.IA (plataforma de IA para agências de marketing: geração de peças, clientes, indicadores, Bíblia/conhecimento, Meta Ads, logs/alertas, planos).

## Escolhas do usuário
- Auth: JWT e-mail/senha + Google social (Emergent-managed)
- IA texto: GPT-5.4 Mini + Claude Sonnet 4.6 (seletor no UI), chave universal Emergent
- Imagens com IA: sim (GPT Image 1)
- Meta Ads: mock visual (piloto)
- Escopo: completo — dashboard, clientes, geração de peças, Bíblia, logs/alertas, indicadores, planos/assinatura

## Arquitetura
- Frontend: React 19 + Tailwind + shadcn/ui + Recharts + framer-motion (tema dark obsidian, pt-BR)
- Backend: FastAPI + MongoDB (motor), JWT httpOnly cookies + sessões Google OAuth
- IA: emergentintegrations (LlmChat streaming SSE; OpenAIImageGeneration gpt-image-1)
- Pagamentos: Stripe sandbox claimable (Flow A), catálogo em BRL (Starter R$97/mês, Pro R$197/mês, Enterprise R$397/mês; anual −20%), webhook /api/stripe/webhook, tax_mode=calc_only com fallback diy (Stripe Tax não suporta BR)
- Reset de senha: e-mail via proxy Emergent (EMERGENT_EMAIL_KEY)

## Personas
- Dono/admin de agência (jussaracavalcante25@gmail.com): gerencia usuários, configurações, integrações
- Operador de agência (member): gera peças, gerencia clientes, consulta Bíblia, acompanha campanhas

## Requisitos núcleo (estáticos)
Multi-tenant por usuário; geração de conteúdo com IA contextualizada por marca; base de conhecimento; indicadores de campanha; monetização por assinatura.

## Implementado (2026-09-16)
- Landing page vendável com pricing
- Auth completo: registro, login, logout, refresh, esqueci/redefinir senha (e-mail real), Google OAuth
- Dashboard com 8 KPIs + gráficos (investimento diário, conversões) + atividade recente
- Clientes CRUD com contexto de marca; página de detalhe
- Gerador de peças com streaming SSE, 6 formatos, 2 modelos, 6 tons, geração de imagem GPT Image 1
- Biblioteca de peças com aprovação/status/filtro
- Bíblia: documentos + Q&A com IA (streaming, chips de fontes)
- Campanhas Meta Ads (mock): cards com dial ROAS, grid/tabela, sync, pausar/ativar, criação
- Logs & Alertas: timeline filtrada, regras de alerta, ocorrências auto-avaliadas no sync
- Configurações: modelo/tom padrão, agência, integrações, gestão de usuários (admin)
- Planos & assinatura Stripe com checkout real + webhook + polling de status
- Dados demo seedados para o admin; testes: backend 28/28 pytest + frontend E2E 100%

## Pendente / Backlog
- P0: nada bloqueante
- P1: completar fluxo de pagamento ponta-a-ponta com cartão 4242 na página hospedada do Stripe (teste de UI); exercitar Claude Sonnet 4.6 no UI; testar geração de imagem no UI
- P1: embeddings reais (RAG vetorial) para a Bíblia em vez de word-overlap
- P2: integração Meta Ads real (Graph API) quando usuário fornecer credenciais
- P2: onboarding de novos usuários com dados demo opcionais
- P2: webhook Stripe em produção (auto na implantação); KYC do sandbox para ir ao ar

## Próximas tarefas
1. Usuário revisar o app e validar geração de imagem no UI
2. Decidir se quer claim do sandbox Stripe (link de onboarding compartilhado) para receber pagamentos reais
3. Priorizar RAG vetorial ou Meta Ads real conforme feedback

## 2026-06 — Paleta Vanguarda aplicada
- Substituído tema indigo/violeta por vermelho Vanguarda (#FF2D40, primary hsl 355 100% 59%) e pretos neutros (#0B0B0D, #15151A) em index.css e todas as páginas.
- Migração para GitHub: orientado a usar "Save to GitHub" (não é possível pelo agente).

## 2026-06 — Preparação para deploy externo (Vercel/Railway/Render)
- Criados arquivos de deploy: backend/Procfile, backend/runtime.txt, backend/.env.example, frontend/.env.example, frontend/vercel.json, render.yaml, DEPLOY.md (guia pt-BR completo: MongoDB Atlas + backend + Vercel + Google OAuth próprio).
- Google OAuth agora CONDICIONAL por env var, sem quebrar o preview:
  - Preview (sem GOOGLE_CLIENT_ID): usa fluxo Emergent-managed (auth.emergentagent.com).
  - Externo (com GOOGLE_CLIENT_ID + REACT_APP_GOOGLE_CLIENT_ID): verifica id_token via google-auth; frontend usa @react-oauth/google (GoogleLogin + GoogleOAuthProvider).
  - Arquivos: backend/server.py (/api/auth/google/session), frontend/src/pages/auth/Login.jsx, frontend/src/index.js.
- Verificado: backend sobe sem erros; tela de login do preview intacta (botão Emergent renderizando).

## 2026-06 — Landing page executiva (redesign com tendências 2026)
- Reescrita frontend/src/pages/Landing.jsx aplicando padrões de conversão SaaS B2B/IA de 2026:
  - Hero 2 colunas com "capability surface" (mock de UI do produto: peça gerada + métricas), no lugar de foto de stock.
  - Banda de stats defensáveis; seções editoriais Produção/Decisão com mocks (gráfico de barras); muro de integrações; copy direta sem fluff.
  - CTA final dedicado + CTA fixo no rodapé (aparece após scroll > 560px). Nav âncora (Recursos/Integrações/Planos).
  - Paleta Vanguarda mantida; animações framer-motion; todos com data-testid.
- Verificado por screenshot: renderiza sem erros de console, sem overflow horizontal.

## 2026-06 — SaaS vendável: cadastro mascarado + publicação simulada
- Landing: removido botão "Começar grátis" (header só "Entrar", hero "Acessar plataforma"); todos os CTAs de /register apontam para /login; CTA fixo simplificado.
- Cadastro público MASCARADO: rota /register redireciona para /login (App.js); removido link "Criar conta" do Login. Acesso só por e-mail/senha ou Google; novas contas criadas pelo admin.
- Publicação SIMULADA (peças e campanhas):
  - Backend: POST /api/pieces/{id}/publish e POST /api/campaigns/{id}/publish com body opcional {scheduled_at} ISO. Sem/agora -> status 'publicada' (peça) / 'ativa' (campanha) + published_at. Futuro -> status 'agendada' + scheduled_at. Log kind 'publicacao'. Model PublishRequest + helper _parse_schedule.
  - Frontend: botões Publicar/Agendar em Pieces.jsx e Campaigns.jsx com dialog de datetime; novo status 'agendada' (roxo) nos mapas; exibição de published_at/scheduled_at.
- Gerador: imagem gerada agora usa object-contain max-h-[75vh] (mostra imagem inteira, sem cortar).
- Validado: backend por curl + testing_agent frontend 100% (iteration_2.json), sem bugs.

## 2026-06 — Gestão de Usuários + logout landing + data mínima
- Backend admin CRUD de usuários (JWT/bcrypt): POST/PUT/DELETE /api/admin/users com proteções — e-mail único, não remover a si mesmo, não rebaixar/remover o último admin, reset de senha incrementa token_version. Models AdminUserCreate/AdminUserUpdate.
- Frontend Settings.jsx: aba "Usuários" (admin) com criar/editar/remover via dialog; email travado no modo edição; coluna Plano exibe label (Trial/Starter/Pro/Enterprise); botão remover do próprio admin desabilitado.
- Logout agora retorna à landing '/': AppLayout.handleLogout navega para '/' (replace) ANTES de await logout(), evitando a corrida com ProtectedRoute.
- Agendamento: inputs datetime-local em Pieces/Campaigns com min=agora (bloqueia datas passadas).
- Validado: backend por curl (guardrails corretos) + testing_agent frontend 100% (iteration_5.json).

## 2026-06 — Security Audit + correções
- Auditoria (security_audit_agent) apontou 1 CRÍTICO + 3 médios; corrigidos:
  - SEC-001 (CRÍTICO): removidas credenciais de admin de arquivos versionados (auth_testing.md, tests/backend_test.py agora lêem de env/backend/.env). git grep confirma limpo.
  - SEC-002: seed_admin não sobrescreve mais a senha de um admin existente (evita reset a cada boot); garante só o papel admin.
  - SEC-003: /api/payments/checkout e /api/payments/status/{id} agora exigem autenticação (Depends get_current_user_id) e derivam user_id do cookie; status valida ownership. Curl: 401 sem auth, 200 com auth.
  - SEC-004: /api/campaigns/{id}/status usa body Pydantic (CampaignStatusUpdate) — força preflight/JSON (mitiga CSRF).
  - Hardening: Google custom OAuth exige email_verified.
- Validado: curl + testing_agent frontend 100% (iteration_6.json), sem regressões.
- PENDENTE (ação do usuário antes de export público no GitHub): rotacionar ADMIN_PASSWORD e limpar o histórico do git das credenciais que já foram commitadas. .env (Stripe/JWT/LLM) está gitignored.

## 2026-06 — Qualidade das peças de IA + modal de revisão
- Texto: reescrito system/prompt de generate_piece — copy publicável de nível sênior, SEM rótulos 'TÍTULO:/LEGENDA:/CTA:'; primeira linha = gancho/título. (corrigido bug de f-string com backslash no Python 3.11).
- Imagem: generate-image agora quality='high' + prompt de criativo profissional. Funciona (~49s local, ~3MB base64). CAVEAT: lento pelo proxy externo (pode passar de 90s ocasionalmente) e imagem pesada armazenada como base64 no doc.
- Peças clicáveis: Pieces.jsx ganhou modal de revisão (piece-review-dialog) — clique no título/thumb/'Revisar peça' abre; mostra conteúdo completo + imagem grande; edição inline (título/conteúdo via PUT) e ações Aprovar/Publicar/Agendar dentro do modal.
- Generator: extração de título passou a usar a primeira linha do stream.
- Validado: curl (texto limpo, imagem high ok) + testing_agent frontend ~95% (iteration_7.json); geração de imagem marcada PARCIAL apenas por lentidão no preview.
- BACKLOG recomendado: mover imagens para object storage (URL em vez de base64) para não inchar GET /pieces nem os documentos.

## 2026-06 — Bíblia: anexos com extração de contexto por IA
- Backend: POST /api/bible/upload (multipart) aceita PDF, DOCX, XLSX, PNG, JPEG, TXT, CSV, MD (máx 15MB). Extração: pypdf/python-docx/openpyxl/decode; imagens via LlmChat ImageContent (vision). Refina com gpt-5.4-mini gerando contexto estruturado pt-BR; salva em bible_documents com campo source_file. Formato inválido -> 400.
- Frontend Bible.jsx: botão "Anexar" + input oculto; durante upload mostra "Processando com IA..."; docs mostram selo com nome do arquivo (Paperclip).
- Libs adicionadas: pypdf, python-docx, openpyxl.
- Validado: curl (docx/xlsx/png ok, unsupported 400) + testing_agent frontend 100% (iteration_8.json).

## Nekt MCP (banco de clientes) — PLUMBING PRONTO, AGUARDA ENDPOINT
- Usuário quer: SINCRONIZAR clientes do Nekt + usar como CONTEXTO IA. Campos: client_id, client_name, client_cnpj, client_group_name.
- Token Bearer salvo em backend/.env (NEKT_MCP_TOKEN). NEKT_MCP_URL="" (VAZIO — precisa do endpoint do app.nekt.ai → Integrations → MCP Server).
- Implementado: backend/nekt.py (cliente MCP JSON-RPC 2.0 sobre HTTP Streamable: initialize/tools/list/tools/call, parsing SSE+JSON). Endpoints admin: GET /api/integrations/nekt/status, POST /api/integrations/nekt/test (list_tools), POST /api/integrations/nekt/sync-clients (execute_sql SELECT client_id,client_name,client_cnpj,client_group_name FROM clients → upsert em db.clients com nekt_id/source).
- Verificado local: status={configured:false,token_set:true}, test=400 claro (URL vazia). NÃO TESTADO end-to-end (falta endpoint). Tabela SQL 'clients' é um palpite — ajustar quando o endpoint permitir list_tables.
- TODO ao receber endpoint: setar NEKT_MCP_URL, rodar /test para ver tools/shape, ajustar SQL/tabela, testar sync, adicionar UI (botão Sincronizar em Clientes) + injeção de contexto Nekt no gerador/bíblia.

## 2026-06 — Nekt conectado + Imagem obedece Bíblia + Spec VJOB
- Nekt CONECTADO + SYNC ATIVO: view real = `vanguardamartech_raw.supabase_public_vw_cliente_entidade_vbot` (~122 clientes; cols customer_id, nome_fantasia, cnpj, grupo_nome, segmento). execute_sql usa param `sql_query`; resultado formato {columns, data}. POST /api/integrations/nekt/sync-clients importa/upserta em db.clients (source=nekt, nekt_id, cnpj, segment, group_name), idempotente. Botão "Sincronizar Nekt" em Clientes (admin). Testado: 129 clientes importados, testing_agent 100% (iteration_9.json). Clientes do Nekt já alimentam o contexto da IA (segment/notes) ao gerar peças.
- FIX Bíblia na imagem: generate-image agora recebe client_id e injeta build_brand_context (inclui docs da Bíblia) como DIRETRIZ OBRIGATÓRIA no prompt. Antes ignorava a Bíblia. Verificado via curl. Regra do usuário: sempre máxima qualidade + obedecer a Bíblia quando preenchida.
- Spec VJOB (anexo ESPECIFICACAO_INTEGRACAO_VJOB): projeto GRANDE e faseado (Strangler; gateway read-only; sync incremental; camada Bronze/Silver/Gold via Nekt; painel admin; RBAC; auditoria). Fase 0 = mocks+flags+painel; conexão real só com credenciais do banco VJOB (mecanismo/host/user readonly/etc — pendentes). NÃO iniciado; aguardando aprovação de escopo/fase.

## 2026-06 — Diagnóstico "base vazia em produção" (RESOLVIDO — não era bug)
- Sintoma: dona relatou base vazia no app publicado. Investigação (deployer read-only): produção tem dados (users 3, clients 4 demo, bible_documents 3, campaigns 7) e TODOS pertencem ao admin jussaracavalcante25@gmail.com (user_4838c2cc5049). Secrets de produção OK (ADMIN_EMAIL=gmail, NEKT_MCP_URL/TOKEN presentes).
- CAUSA RAIZ: ela logou com o e-mail de trabalho jussara.cavalcante@vanguardamartech.com.br, que é conta MEMBER separada e sem dados -> base aparece vazia. Sem bug de auth/filtro (queries filtram por user_id corretamente).
- Clientes reais (133) e Bíblia estão só no PREVIEW; produção nunca rodou Sincronizar Nekt (source=nekt inexistente em prod).
- CORREÇÃO DE CÓDIGO (aplicada, testada local, AGUARDA REPUBLICAÇÃO pela usuária): server.py ganhou _is_owner_email() + ensure_owner_admin(); qualquer login (Google/senha) do e-mail ADMIN_EMAIL é promovido a admin/agency automaticamente. Chamado em /auth/login, /auth/google/session (ambos os fluxos) e na criação de conta Google.
- AÇÃO PENDENTE DO USUÁRIO em produção: (1) republicar; (2) logar com jussaracavalcante25@gmail.com; (3) Clientes -> Sincronizar Nekt (importa 133); (4) subir docs da Bíblia manualmente.

## 2026-06 — Qualidade de imagem = nível ChatGPT (expansão de prompt)
- PROBLEMA: imagem gerada no app tinha qualidade inferior à do ChatGPT (composição pobre/achatada) mesmo já usando gpt-image-1 quality=high. CAUSA: prompt enviado era genérico; o ChatGPT auto-expande o briefing em direção de arte detalhada.
- FIX: nova função expand_image_prompt() (server.py) — usa LLM de TEXTO (gpt-5.4-mini, barato em créditos, NÃO gera imagens extras) para transformar o briefing curto + contexto da Bíblia num prompt de direção de arte rico em inglês (sujeitos, cena, props, composição, luz, paleta, estilo, tipografia on-image, quality descriptors, no watermark). generate-image passa esse prompt ao gpt-image-1 quality=high (1 imagem). Regra do usuário: economizar créditos.
- Verificado com 1 geração (curl localhost, ~57s, 2.6MB): resultado rico com headline/subheadline/CTA integrados, obedecendo a Bíblia. Match com ChatGPT.
- LIMITAÇÃO CONHECIDA (pré-existente): geração high leva ~55s; o proxy de ingress externo pode retornar 502 por timeout antes de concluir. Não afeta qualidade. Mitigação futura sugerida: geração assíncrona com polling (job + status) para evitar timeout do proxy.

## 2026-06 — Geração de imagem assíncrona (fim do 502) + barra de progresso
- Backend: POST /api/pieces/generate-image agora cria job em db.image_jobs (status processing) e dispara asyncio.create_task(_run_image_job) — retorna {job_id, status} na hora (sem esperar ~55s). GET /api/pieces/image-job/{job_id} devolve status/image/error; ao ficar done/error o job é deletado (evita bloat de base64). expand_image_prompt continua na geração.
- Frontend Generator.jsx: generateImage faz POST -> polling a cada 3s no job até done/error; barra de Progress (shadcn) com % simulado subindo até 92% em ~60s e 100% ao concluir. data-testid: image-progress, image-progress-bar. Usuário pode navegar durante a geração.
- Verificado ponta a ponta via URL EXTERNA: POST 200 imediato, polling entrega imagem 3.7MB sem 502. Frontend compila (login OK).

## 2026-06 — Campo de pesquisa em Clientes + análise de usabilidade
- Clients.jsx: adicionado campo de busca (data-testid=clients-search-input) que filtra client-side por name, segment, cnpj, group_name, contact_name, contact_email. Mostra contador "X de Y" e estado "nenhum encontrado" (clients-no-results). Essencial com 133 clientes. Frontend compiled successfully.
- OBS: verificação visual via screenshot tool ficou inconclusiva (tool exibia a tela de login pós-navegação); validado por compilação + leitura de código. Lógica é filtro puro no front.

## 2026-06 — Correções de usabilidade (frontend-only)
- AppLayout: menu mobile refeito. Antes era uma fileira de 9 ícones sem rótulo em overflow-x. Agora é um botão hambúrguer (data-testid=mobile-menu-trigger) que abre um Sheet lateral (data-testid=mobile-menu) com itens rotulados + logo + botão Sair (mobile-logout). NavLinks mantêm testid `${testid}-mobile`.
- Generator: botão de imagem agora permite REFAZER (aparece mesmo com imagem gerada; label "Refazer imagem"). Antes sumia após a 1a geração.
- Acessibilidade/clareza: title + aria-label adicionados em botões só-ícone: excluir peça (lista e modal), agendar campanha, sincronizar Meta Ads (linha da tabela), remover documento da Bíblia, remover regra de alerta.
- Verificação: frontend "Compiled successfully". Validação visual das telas autenticadas ficou limitada pelo tool de screenshot (captura só a tela de login). Edições são triviais e compilaram.

## 2026-06 — Custeio de IA por peça / refação / etapa (R$ + markup)
- Decisões do usuário: moeda R$; markup configurável (custo interno + preço a faturar); escopo só a peça; tabela de preços editável em Configurações; exibir em Peça + Dashboard + Relatório por cliente. Mostrado ao usuário ANTES de implementar (aprovado). Implementado só no PREVIEW; usuário republica.
- Backend (server.py): DEFAULT_PRICING (usd_to_brl=5.40, markup_pct=100, image_high_per_unit=0.19, models gpt-5.4-mini 0.15/0.60, claude-sonnet-4-6 3.0/15.0 US$/1M). Helpers get_pricing/_text_cost_usd/record_cost/stage_for. Coleção ai_costs {gen_group_id, piece_id, client_id, stage, model, tokens, images, cost_usd, cost_brl}. Etapas: copy, refacao_texto, imagem, refacao_imagem (stage_for detecta refação por contagem no mesmo gen_group_id). generate_piece captura StreamDone.usage e emite no SSE {done,stage,cost_brl,tokens}. _run_image_job soma custo da imagem + expansão de prompt e grava cost_brl no job. save_piece vincula ai_costs (gen_group_id->piece_id), grava cost_brl/regen_count/cost_breakdown e billable_brl. list_pieces/dashboard(ai_cost_brl,ai_billable_brl)/GET /reports/costs (agregado por cliente) + get_settings/update_settings com pricing.
- Frontend: Generator painel 'Custo desta peça (IA)' por etapa em tempo real (genGroupId via crypto.randomUUID). Pieces: chip de custo + bloco 'Custo de IA por etapa' (Interno/Faturar) no modal. Dashboard: KPIs kpi-ai-cost/kpi-ai-billable. Nova página /custos (Reports.jsx, item nav-custos): totais + margem + tabela por cliente. Settings aba 'Custos & Preços' (admin) edita tabela+markup. lib/api.js formatBRLPrecise (mostra até 4 casas p/ valores < R$0,01).
- Testado (iteration_11): 100% backend (9/9 pytest) e 100% frontend (7/7). test file: /app/backend/tests/test_ai_costs.py. Custos de texto ~R$0,001/peça (esperado); imagem ~R$1,03.
- Observação não-bloqueante: coluna 'Peças' do relatório pode subcontar entre gerar e salvar (piece_id só é vinculado ao salvar).

## 2026-06 — Agentes Operacionais (human-in-the-loop): Social, Inbound, Mídia Paga, Account
- Escopo escolhido pelo usuário: 4 agentes (setores social, inbound, account, mídia paga); modelo escolhido a cada execução (Claude Sonnet 4.6 ou GPT-5.4 Mini); Aprovar aplica ação real; Account envia e-mail real (Resend gerenciado). Claude já estava integrado (sem nova integração).
- Backend (server.py): AGENTS registry; POST /api/agents/{key}/run gera PROPOSTA (JSON estruturado via LLM) status 'pendente' (coleção agent_proposals); GET /api/agents/proposals; PUT (editar payload); POST .../approve -> _apply_proposal executa: social/inbound criam pieces rascunho, midia_paga cria campanhas (metrics seed), account envia e-mail via send_email (Resend, guardrails G1-G5). POST .../reject; DELETE. Custo de cada execução registrado com stage 'agente' (aparece em /custos e Dashboard).
- Email: send_email + _assert_safe_email (playbook Resend gerenciado), usa EMERGENT_EMAIL_KEY/EMAIL_FROM_NAME (presentes em .env e produção). Testado com delivered@resend.dev (email_id retornado OK).
- Frontend: nova página /agentes (Agents.jsx), item nav-agentes (ícone Bot), rota em App.js. Cards dos agentes + dialog de execução (cliente/modelo/quantidade/instruções) + fila de aprovação com filtros (pendente/aprovado/rejeitado) e ações Aprovar/Rejeitar/Excluir. Aprovação atualiza o card via resposta da API (determinístico).
- Testado: backend por curl (4 agentes geram proposta; approve cria 2 peças / 2 campanhas; email enviado). Frontend testing_agent iteration_12: 7/8 PASS; o 1 issue (UI não refletia aprovação) FOI CORRIGIDO trocando refetch por atualização de estado com a resposta do approve (verificado: approve retorna status aprovado + result instantâneo).
- test files: /app/test_reports/iteration_12.json

## 2026-06 — Aprovar em Lote + Agente de Otimização + Agendamento de agentes
- APROVAR/REJEITAR EM LOTE: POST /api/agents/proposals/bulk {ids, action}. Frontend: barra bulk-bar com bulk-select-all, checkboxes proposal-select-<id>, bulk-approve/bulk-reject.
- 5º AGENTE OTIMIZAÇÃO: lê métricas 14d das campanhas do cliente e recomenda pausar/ativar/escalar/reduzir (JSON com campaign_id válido). Aprovar aplica: status pausada/ativa ou ajusta budget_daily (budget_new ou ±20%). Adicionado em AGENTS, _agent_generate, _apply_proposal. Card agent-card-otimizacao.
- AGENDAMENTO (crons plataforma): coleção agent_schedules (agent_key, client_id, model, frequency daily/weekly, weekday 0=Dom..6=Sáb, hour UTC, active, last_run_key idempotência). CRUD /api/agents/schedules (GET/POST/PATCH/DELETE). Cron endpoint POST /api/cron/agents-run (auth Bearer WEBHOOK_CRON_SECRET via hmac.compare_digest, ack imediato + asyncio background _run_due_schedules que cria propostas pendentes). Arquivo /app/.emergent/crons.yml (agents-scheduler, "0 * * * *" hourly). WEBHOOK_CRON_SECRET no backend/.env. Frontend: seção Agendamentos (schedule-new dialog, schedules-list, toggle/delete).
- Testado: backend por curl (bulk approved=2; otimizacao optimized_campaigns=4; cron disparou 401/401/200 e criou proposta agendada) e frontend testing_agent iteration_13 = 100% (as 3 features). Corrigido bug: decorator @api_router.get("/agents") havia sido removido por engano e foi restaurado.
- test files: /app/test_reports/iteration_13.json
