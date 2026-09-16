# 🚀 Guia de Deploy Externo — Vanguarda.IA

Este guia leva a aplicação para fora do Emergent, usando:

| Componente | Onde hospedar | Custo inicial |
|---|---|---|
| Frontend (React) | **Vercel** | Grátis |
| Backend (FastAPI) | **Railway** ou **Render** | Grátis (com limites) |
| Banco de dados | **MongoDB Atlas** | Grátis (512MB) |

Arquivos já preparados neste repositório:
- `backend/Procfile` — comando de start do backend
- `backend/runtime.txt` — versão do Python
- `backend/.env.example` — modelo das variáveis do backend
- `frontend/.env.example` — modelo das variáveis do frontend
- `frontend/vercel.json` — config do Vercel (SPA rewrite)
- `render.yaml` — blueprint pronto para o Render

---

## Passo 1 — Banco de dados (MongoDB Atlas)

1. Acesse **https://www.mongodb.com/atlas** → crie conta grátis.
2. Crie um **Cluster gratuito (M0)**.
3. Em **Database Access** → crie um usuário e senha.
4. Em **Network Access** → adicione `0.0.0.0/0` (acesso de qualquer IP).
5. **Connect → Drivers** → copie a connection string:
   ```
   mongodb+srv://usuario:senha@cluster.xxxx.mongodb.net
   ```
   Guarde: será a variável `MONGO_URL`.

---

## Passo 2 — Backend (Railway)

1. Acesse **https://railway.app** → login com GitHub.
2. **New Project → Deploy from GitHub repo** → escolha seu repositório.
3. Em **Settings**:
   - **Root Directory**: `backend`
   - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
4. Em **Variables**, adicione todas as chaves do `backend/.env.example`:
   - `MONGO_URL` = string do Atlas
   - `DB_NAME` = `vanguarda`
   - `CORS_ORIGINS` = URL do frontend no Vercel (ex: `https://vanguarda.vercel.app`)
   - `JWT_SECRET` = string aleatória longa
   - `ADMIN_EMAIL` = `jussaracavalcante25@gmail.com`
   - `ADMIN_PASSWORD` = sua senha
   - `EMERGENT_LLM_KEY`, `STRIPE_*`, etc.
5. O Railway gera uma URL pública, ex: `https://vanguarda-backend.up.railway.app`.

> **Alternativa — Render:** o arquivo `render.yaml` já está pronto. No Render clique em **New → Blueprint**, selecione o repositório e ele lê o `render.yaml` automaticamente. Depois preencha as variáveis marcadas como `sync: false`.

---

## Passo 3 — Frontend (Vercel)

1. Acesse **https://vercel.com** → **Add New → Project** → importe o repositório.
2. Configure:
   - **Root Directory**: `frontend`
   - **Framework Preset**: Create React App
3. Em **Environment Variables**:
   ```
   REACT_APP_BACKEND_URL = https://vanguarda-backend.up.railway.app
   ```
   (a URL do backend do Passo 2 — **sem barra `/` no final**)
4. **Deploy**.

---

## Passo 4 — Configurar o Google Login (OAuth próprio)

⚠️ **Importante:** o login com Google que roda hoje no preview usa o serviço gerenciado do Emergent (`auth.emergentagent.com`) e **só funciona dentro do Emergent**. Fora dele, você precisa das suas próprias credenciais Google.

### 4.1 — Criar credenciais no Google Cloud Console

1. Acesse **https://console.cloud.google.com** → crie um projeto.
2. **APIs & Services → OAuth consent screen** → configure (External) com nome do app e seu e-mail.
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID → Web application**.
4. Em **Authorized JavaScript origins**, adicione:
   ```
   https://vanguarda.vercel.app          (URL do seu frontend)
   ```
5. Em **Authorized redirect URIs**, adicione:
   ```
   https://vanguarda.vercel.app/auth/google
   ```
   (troque pelo domínio final; se usar domínio próprio, adicione-o também)
6. Copie o **Client ID** e o **Client Secret** → coloque nas variáveis
   `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` do backend.

### 4.2 — Trocar o código do login Google (aplicar só na hospedagem externa)

O código atual do backend (`server.py`, rota `/api/auth/google/session`) chama o Emergent.
Substitua-o pela verificação direta do token do Google. Instale a dependência:

```bash
pip install google-auth
```

**Backend — nova rota** (substitui a `google_session` atual):

```python
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

@api_router.post("/auth/google/session")
async def google_session(request: Request, response: Response):
    body = await request.json()
    credential = body.get("credential")  # JWT id_token vindo do Google
    if not credential:
        raise HTTPException(status_code=400, detail="credential ausente")
    try:
        data = google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), os.environ["GOOGLE_CLIENT_ID"]
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Token Google inválido")

    email = data["email"].lower()
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id, "email": email,
            "name": data.get("name", email.split("@")[0]),
            "picture": data.get("picture"), "role": "member", "plan": "trial",
            "token_version": 0, "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user)
    # emite os mesmos cookies JWT do login normal:
    set_jwt_cookies(response, user)
    return public_user(user)
```

**Frontend — botão do Google** (`frontend/src/pages/auth/Login.jsx`):

```bash
yarn add @react-oauth/google
```

Envolva o app com o provider em `src/index.js` ou `App.js`:

```jsx
import { GoogleOAuthProvider } from "@react-oauth/google";
<GoogleOAuthProvider clientId={process.env.REACT_APP_GOOGLE_CLIENT_ID}>
  <App />
</GoogleOAuthProvider>
```

Troque o `GoogleButton` por:

```jsx
import { GoogleLogin } from "@react-oauth/google";

export function GoogleButton() {
  const { setUser } = useAuth();
  return (
    <GoogleLogin
      onSuccess={async (resp) => {
        const { data } = await api.post("/auth/google/session", {
          credential: resp.credential,
        });
        setUser(data);
        window.location.href = "/dashboard";
      }}
      onError={() => toast.error("Falha no login com Google")}
    />
  );
}
```

E adicione no `frontend/.env` do Vercel:
```
REACT_APP_GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
```

---

## Passo 5 — Ajustes finais

1. **Stripe:** rode uma vez o script para recriar o catálogo no banco novo:
   ```bash
   cd backend && python setup_stripe.py
   ```
2. **Conta admin:** o banco novo está vazio. O backend cria o admin no startup usando `ADMIN_EMAIL` / `ADMIN_PASSWORD`. Confirme que essas variáveis estão setadas no Railway/Render.
3. **CORS:** já vem como `*` no código, mas para produção coloque em `CORS_ORIGINS` a URL exata do Vercel.
4. **Cookies entre domínios:** frontend (Vercel) e backend (Railway) ficam em domínios diferentes. Os cookies já usam `SameSite=None; Secure`, então funcionam desde que ambos estejam em HTTPS (o que Vercel e Railway garantem).

---

## Checklist final
- [ ] MongoDB Atlas criado e `MONGO_URL` copiada
- [ ] Backend no Railway/Render rodando (testar `https://.../api/` )
- [ ] Frontend no Vercel com `REACT_APP_BACKEND_URL` apontando para o backend
- [ ] Google OAuth próprio configurado (Passo 4)
- [ ] `setup_stripe.py` executado
- [ ] Login admin funcionando

> 💡 **Alternativa muito mais simples:** publicar direto no Emergent com **domínio personalizado** — tudo (backend, banco, Google Auth, Stripe) continua funcionando sem reconfigurar nada. Use este guia apenas se realmente precisar hospedar fora do Emergent.
