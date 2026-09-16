# Implantação na Vercel — Vanguarda.IA

Guia operacional para colocar a aplicação no ar. O repositório é um monorepo:
o frontend e o backend viram **dois projetos Vercel separados**, apontando para
o mesmo repositório com *Root Directory* diferentes.

---

## 1. Pré-requisitos que só você pode provisionar

| # | Item | Por quê | Onde |
|---|---|---|---|
| 1 | **Banco MongoDB** | A Vercel não hospeda banco de dados. Sem ele a aplicação não sobe. | MongoDB Atlas — tier gratuito M0 atende |
| 2 | **Saldo nas contas de IA** | As chaves autenticam, mas ambas as contas estão sem crédito. | console.anthropic.com · platform.openai.com |
| 3 | **Conta Vercel** | Plano Hobby já permite 300s de duração por função. | vercel.com |
| 4 | *(opcional)* Chaves Stripe | Só para a tela de Planos/assinatura. | dashboard.stripe.com |

### MongoDB Atlas — configuração mínima

1. Crie um cluster **M0 (gratuito)**, região `sa-east-1` (São Paulo) ou `us-east-1`.
2. Em **Database Access**, crie um usuário com senha.
3. Em **Network Access**, libere `0.0.0.0/0`.
   As funções da Vercel usam IPs dinâmicos — não há faixa fixa para liberar no
   plano Hobby. Se isso for inaceitável para a sua política de segurança, o
   caminho é *Static IPs* (plano Enterprise) ou hospedar o backend em um
   provedor com IP fixo.
4. Copie a *connection string*: `mongodb+srv://usuario:senha@cluster.xxxx.mongodb.net/`

---

## 2. Projeto do backend

**Vercel → Add New → Project → importe o repositório**

| Configuração | Valor |
|---|---|
| Project Name | `vanguarda-api` (sugestão) |
| **Root Directory** | **`backend`** |
| Framework Preset | *Other* (a Vercel detecta o FastAPI automaticamente) |

A Vercel procura uma instância `FastAPI` chamada `app` em nomes de arquivo
suportados — `server.py` é um deles, então não é preciso criar `api/index.py`
nem apontar entrypoint. O `backend/vercel.json` já define `maxDuration: 300`,
necessário porque a geração de peça é uma resposta em streaming.

### Variáveis de ambiente (Settings → Environment Variables)

```
MONGO_URL           mongodb+srv://usuario:senha@cluster.xxxx.mongodb.net/
DB_NAME             vanguarda_ia
JWT_SECRET          <gere: python3 -c "import secrets; print(secrets.token_urlsafe(48))">
FRONTEND_URL        https://vanguarda-web.vercel.app     <- URL do projeto do frontend
ADMIN_EMAIL         voce@suaagencia.com.br
ADMIN_PASSWORD      <senha forte>
ANTHROPIC_API_KEY   sk-ant-...
OPENAI_API_KEY      sk-proj-...
COOKIE_SECURE       true
COOKIE_SAMESITE     none
STRIPE_SECRET_KEY        <opcional>
STRIPE_WEBHOOK_SECRET    <opcional>
```

> `COOKIE_SECURE=true` e `COOKIE_SAMESITE=none` são obrigatórios nesta
> arquitetura: o frontend e o backend ficam em domínios diferentes, então o
> cookie de sessão é *cross-site*. Ambos já são o padrão do código.

---

## 3. Projeto do frontend

**Vercel → Add New → Project → importe o MESMO repositório**

| Configuração | Valor |
|---|---|
| Project Name | `vanguarda-web` (sugestão) |
| **Root Directory** | **`frontend`** |
| Framework Preset | *Create React App* |
| Build Command | `yarn build` (padrão) |
| Output Directory | `build` (padrão) |

### Variável de ambiente

```
REACT_APP_BACKEND_URL   https://vanguarda-api.vercel.app    <- URL do backend, SEM barra final
```

> Variáveis `REACT_APP_*` são embutidas no bundle **em tempo de build**.
> Trocar o valor exige um novo deploy — não basta salvar no dashboard.

O `frontend/vercel.json` já traz o *rewrite* que devolve `index.html` para
qualquer rota, sem o qual recarregar `/gerar` ou `/campanhas` resultaria em 404
(o roteamento é client-side, via `BrowserRouter`).

---

## 4. Ordem de execução

Há uma dependência circular de URLs: o backend precisa saber a URL do frontend
(CORS) e o frontend precisa saber a do backend. Resolva assim:

1. Crie o projeto do **backend** com um `FRONTEND_URL` provisório.
2. Crie o projeto do **frontend** já com a `REACT_APP_BACKEND_URL` real.
3. Volte ao backend, corrija `FRONTEND_URL` com a URL real do frontend.
4. **Faça redeploy do backend** para a variável valer.

---

## 5. Pontos de atenção conhecidos

| Assunto | Situação |
|---|---|
| **Deployments de preview** | O CORS do backend libera apenas `FRONTEND_URL` e `localhost:3000`. URLs de preview da Vercel são aleatórias e serão **bloqueadas**. Só a URL de produção funciona sem ajuste no código. |
| **Geração de imagem** | O limite de corpo de resposta da Vercel é **4,5 MB**. A imagem volta em base64 (≈ +33% sobre o tamanho bruto). Imagens grandes podem estourar e retornar `FUNCTION_PAYLOAD_TOO_LARGE`. |
| **Tamanho do bundle** | Resolvido. O limite Python é 500 MB e as dependências foram reduzidas a 124 MB — ver seção 6. |
| **Login com Google** | Ainda aponta para `auth.emergentagent.com` (`frontend/src/pages/auth/Login.jsx:15`). Vai falhar. O login por e-mail/senha funciona normalmente. |
| **Reset de senha por e-mail** | Depende do proxy da Emergent. Fica inativo. |
| **Seeding** | Roda a cada cold start, mas é idempotente (verifica existência antes de inserir). Não duplica dados. |
| **Cookies de terceiros** | `SameSite=none` é cookie *cross-site*. Navegadores vêm restringindo esse tipo. Se o login parar de funcionar no futuro, a solução é servir tudo sob o mesmo domínio. |

---

## 6. Dependências do backend (já enxugadas)

O `requirements.txt` original tinha **125 pacotes** — um `pip freeze` completo
da imagem da Emergent. A superfície real de imports do backend é de 12 pacotes.

A lista foi reduzida a **15 entradas explícitas**, derivadas dos imports de
`server.py`, `payments.py` e `emergentintegrations/`. As ferramentas de teste
passaram para `requirements-dev.txt`, que não entra no bundle da função.

Removidos por não serem usados: `pandas`, `numpy`, `boto3`, `botocore`,
`google-generativeai`, `google-genai`, `grpcio`, `huggingface_hub`,
`tokenizers`, `tiktoken`, `litellm`, além de `black`, `mypy`, `flake8`,
`isort` e `pytest`.

Duas dependências foram mantidas por motivo específico, apesar de não
aparecerem em nenhum `import`:

- **`dnspython`** — obrigatório para URIs `mongodb+srv://`. Sem ele a conexão
  com o MongoDB Atlas falha.
- **`email-validator`** — exigido por `pydantic.EmailStr`, usado nos modelos
  de autenticação.

### Verificação executada

A lista foi validada em ambiente virtual limpo, instalado do zero:

| Métrica | Antes | Depois |
|---|---|---|
| Entradas no `requirements.txt` | 125 | 15 |
| Pacotes instalados (com transitivos) | — | 36 |
| Peso de `site-packages` | — | **124 MB** (teto da Vercel: 500 MB) |
| Suíte de regressão | 25/28 | **25/28** (idêntica) |

As 3 falhas remanescentes são as mesmas de antes e dependem apenas de
credenciais: geração de peça e consulta à Bíblia exigem saldo nas contas de
IA; a listagem de planos exige `STRIPE_SECRET_KEY`.

### Instalação local para desenvolvimento

```bash
pip install -r backend/requirements-dev.txt   # inclui o requirements.txt
```

---

## 7. Validação pós-deploy

```bash
API=https://vanguarda-api.vercel.app

curl -s -o /dev/null -w "docs: %{http_code}\n"    $API/docs
curl -s -o /dev/null -w "auth: %{http_code}\n"    $API/api/auth/me     # 401 esperado

curl -s -i -X POST $API/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"SEU_ADMIN","password":"SUA_SENHA"}' | grep -i "^set-cookie"
```

O `set-cookie` deve conter `Secure` e `SameSite=none`. Se não contiver, as
variáveis de cookie não foram aplicadas — refaça o deploy do backend.

Depois, no navegador: abrir o frontend, entrar, e conferir que `/dashboard`,
`/clientes`, `/campanhas` e `/biblia` carregam dados.
