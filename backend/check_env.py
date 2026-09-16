#!/usr/bin/env python3
"""Verificador de configuração — rode antes de implantar.

Confere as variáveis de ambiente obrigatórias e testa de verdade a conexão com
o MongoDB, apontando a causa provável quando algo falha. Não escreve nada no
banco e não imprime segredo algum.

Uso:
    python3 backend/check_env.py                    # lê backend/.env
    MONGO_URL="mongodb+srv://..." python3 backend/check_env.py
"""

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

VERDE, VERM, AMAR, CINZA, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[90m", "\033[0m"
OK, ERRO, AVISO = f"{VERDE}  OK  {RESET}", f"{VERM} ERRO {RESET}", f"{AMAR} AVISO{RESET}"

falhas = 0
avisos = 0


def linha(status: str, nome: str, detalhe: str = "") -> None:
    print(f"[{status}] {nome:22} {CINZA}{detalhe}{RESET}")


def exigir(nome: str, dica: str) -> str:
    global falhas
    v = (os.environ.get(nome) or "").strip()
    if not v:
        linha(ERRO, nome, f"ausente — {dica}")
        falhas += 1
        return ""
    linha(OK, nome, f"definida ({len(v)} chars)")
    return v


def opcional(nome: str, consequencia: str) -> str:
    global avisos
    v = (os.environ.get(nome) or "").strip()
    if not v:
        linha(AVISO, nome, f"ausente — {consequencia}")
        avisos += 1
        return ""
    linha(OK, nome, f"definida ({len(v)} chars)")
    return v


def main() -> int:
    global falhas

    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(env_file)
            print(f"{CINZA}Carregado: {env_file}{RESET}\n")
        except ImportError:
            print(f"{CINZA}python-dotenv ausente; lendo apenas o ambiente{RESET}\n")
    else:
        print(f"{CINZA}Sem backend/.env; lendo apenas o ambiente{RESET}\n")

    print("── Obrigatórias ──")
    mongo_url = exigir("MONGO_URL", "sem banco a aplicação não sobe")
    exigir("DB_NAME", "nome do banco, ex.: vanguarda_ia")
    segredo = exigir("JWT_SECRET", 'gere: python3 -c "import secrets; print(secrets.token_urlsafe(48))"')
    front = exigir("FRONTEND_URL", "usada no CORS; sem ela o navegador bloqueia as chamadas")
    email_admin = exigir("ADMIN_EMAIL", "administrador semeado no primeiro start")
    exigir("ADMIN_PASSWORD", "senha do administrador")

    if segredo and len(segredo) < 32:
        linha(AVISO, "JWT_SECRET", "curto demais — use ao menos 32 caracteres")
    if front and not front.startswith(("http://", "https://")):
        linha(ERRO, "FRONTEND_URL", "precisa incluir o esquema (https://)")
        falhas += 1
    if front.endswith("/"):
        linha(AVISO, "FRONTEND_URL", "barra final costuma quebrar a checagem de CORS")
    if email_admin and email_admin.rsplit(".", 1)[-1] in {"local", "test", "invalid", "example"}:
        linha(ERRO, "ADMIN_EMAIL", "domínio reservado é recusado pelo validador de e-mail")
        falhas += 1

    print("\n── Provedores de IA ──")
    tem_anthropic = bool(opcional("ANTHROPIC_API_KEY", "o modelo Claude Sonnet 4.6 falhará"))
    tem_openai = bool(opcional("OPENAI_API_KEY", "o GPT-5.4 Mini e a geração de imagem falharão"))
    if not tem_anthropic and not tem_openai:
        linha(ERRO, "provedores de IA", "nenhuma chave definida — nenhuma geração funcionará")
        falhas += 1

    print("\n── Opcionais ──")
    opcional("STRIPE_SECRET_KEY", "a tela de Planos retornará erro 500")
    for nome, padrao, nota in [
        ("COOKIE_SECURE", "true", "use true em produção (HTTPS)"),
        ("COOKIE_SAMESITE", "none", "use none quando frontend e backend estão em domínios diferentes"),
    ]:
        v = (os.environ.get(nome) or "").strip() or f"{padrao} (padrão)"
        linha(OK, nome, f"{v} — {nota}")

    print("\n── Conexão com o MongoDB ──")
    if not mongo_url:
        linha(ERRO, "conexão", "pulada, MONGO_URL ausente")
        return encerrar()

    esquema = urlparse(mongo_url).scheme
    if esquema == "mongodb+srv":
        try:
            import dns  # noqa: F401

            linha(OK, "dnspython", "presente — necessário para mongodb+srv://")
        except ImportError:
            linha(ERRO, "dnspython", "AUSENTE — mongodb+srv:// não resolve sem ele")
            falhas += 1
    elif esquema != "mongodb":
        linha(ERRO, "MONGO_URL", f"esquema inesperado: {esquema!r}")
        falhas += 1

    try:
        from pymongo import MongoClient
        from pymongo.errors import (
            ConfigurationError,
            OperationFailure,
            ServerSelectionTimeoutError,
        )
    except ImportError:
        linha(ERRO, "pymongo", "não instalado — pip install -r backend/requirements.txt")
        return encerrar()

    try:
        cliente = MongoClient(mongo_url, serverSelectionTimeoutMS=10000)
        info = cliente.server_info()
        linha(OK, "conexão", f"MongoDB {info.get('version', '?')} respondeu")
        nome_db = (os.environ.get("DB_NAME") or "vanguarda_ia").strip()
        colecoes = cliente[nome_db].list_collection_names()
        linha(OK, "banco", f"{nome_db}: {len(colecoes)} coleções")
    except OperationFailure as e:
        linha(ERRO, "autenticação", f"usuário ou senha recusados ({e.code})")
        print(f"{CINZA}       Senha com caractere especial precisa de percent-encoding na URI.{RESET}")
        falhas += 1
    except ServerSelectionTimeoutError:
        linha(ERRO, "conexão", "servidor inalcançável em 10s")
        print(f"{CINZA}       No Atlas, confira Network Access: as funções da Vercel usam IP dinâmico.{RESET}")
        falhas += 1
    except ConfigurationError as e:
        msg = str(e)
        if "DNS" in msg or "does not exist" in msg:
            linha(ERRO, "DNS", "o host do cluster não resolve")
            print(f"{CINZA}       Confira o nome do cluster na URI copiada do Atlas.{RESET}")
        else:
            linha(ERRO, "URI", f"malformada: {msg[:70]}")
        falhas += 1
    except Exception as e:  # noqa: BLE001
        linha(ERRO, "conexão", f"{type(e).__name__}: {str(e)[:70]}")
        falhas += 1

    return encerrar()


def encerrar() -> int:
    print()
    if falhas:
        print(f"{VERM}{falhas} problema(s) impeditivo(s). Corrija antes de implantar.{RESET}")
        return 1
    if avisos:
        print(f"{AMAR}Configuração utilizável, com {avisos} ressalva(s) acima.{RESET}")
        return 0
    print(f"{VERDE}Configuração completa. Pronto para implantar.{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
