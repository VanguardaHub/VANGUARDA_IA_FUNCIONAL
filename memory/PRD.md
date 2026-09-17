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
