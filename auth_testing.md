# Auth Testing Playbook — Vanguarda.IA

App URL: https://marketplace-app-463.preview.emergentagent.com
Backend: mesma URL com prefixo /api. Banco MongoDB: `test_database` (via MONGO_URL local: mongodb://localhost:27017).

## Credenciais (NÃO versionar aqui — ver /app/memory/test_credentials.md, que é gitignored)
- Admin: consulte /app/memory/test_credentials.md

## Step 1: MongoDB Verification
mongosh --eval "
use('test_database');
print(db.users.find({role: 'admin'}).count());
print(JSON.stringify(db.users.findOne({role: 'admin'}, {password_hash: 1}).password_hash).slice(0, 10));
"
Verificar: hash bcrypt começa com `$2b$`; índices em users.email (unique), login_attempts.identifier, password_reset_tokens.token_hash (unique).

## Step 2: API Testing (exporte ADMIN_EMAIL/ADMIN_PASSWORD de /app/backend/.env; não cole credenciais aqui)
curl -c /tmp/cookies.txt -X POST "$BACKEND/api/auth/login" -H "Content-Type: application/json" -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}"
curl -b /tmp/cookies.txt "$BACKEND/api/auth/me"
Deve retornar o usuário. Cookies access_token + refresh_token setados.

## Step 3: Password Reset
Para obter um token de teste: temporariamente FRONTEND_URL="http://localhost:3000" em /app/backend/.env + `sudo supervisorctl restart backend`; o link de reset completo será logado em /var/log/supervisor/backend.*.log. Registrar conta nova, chamar forgot-password para ela, pegar o token do log, completar reset-password, verificar login com nova senha e falha com a antiga. RESTAURAR FRONTEND_URL para https://marketplace-app-463.preview.emergentagent.com e reiniciar ao final.

## Step 4: Google Auth
Fluxo Emergent OAuth: botão redireciona para auth.emergentagent.com. Não é testável em automação sem conta Google real — validar apenas que o botão existe e gera a URL correta.

## Endpoints principais (todos exigem cookie/bearer)
- GET /api/dashboard
- GET/POST/PUT/DELETE /api/clients[/id]
- POST /api/pieces/generate (SSE stream) — body: {client_id, piece_type, model: gpt-5.4-mini|claude-sonnet-4-6, tone, prompt}
- POST /api/pieces/generate-image {prompt}
- GET/POST /api/pieces, PUT/DELETE /api/pieces/{id}
- GET/POST/DELETE /api/bible/documents[/id], POST /api/bible/ask (SSE)
- GET/POST /api/campaigns, POST /api/campaigns/{id}/sync, POST /api/campaigns/{id}/status
- GET /api/logs, GET/POST/DELETE /api/alerts/rules
- GET/PUT /api/settings, GET /api/admin/users (admin only)
- POST /api/payments/checkout {lookup_key, origin_url, user_id} — lookup_keys: starter_monthly/yearly, pro_monthly/yearly, agency_monthly/yearly
- GET /api/payments/status/{session_id}
- POST /api/stripe/webhook
