"""Chat multi-provedor com streaming — implementação nativa.

Substitui `emergentintegrations.llm.chat` preservando exatamente o contrato
consumido por `server.py`, de modo que nenhuma linha daquele arquivo precise
mudar.

Resolução de credenciais (primeira que existir vence):
  - provider "anthropic": ANTHROPIC_API_KEY  -> api_key passada ao construtor
  - provider "openai":    OPENAI_API_KEY     -> api_key passada ao construtor

O fallback para a `api_key` do construtor mantém compatibilidade com a chave
universal EMERGENT_LLM_KEY: quem já roda na Emergent continua funcionando.
"""

import os
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

# Teto de tokens por peça. Generoso para qualquer formato do catálogo
# (post, stories, anúncio, e-mail, artigo de blog) sem truncar no meio.
MAX_OUTPUT_TOKENS = 8192


@dataclass
class UserMessage:
    """Mensagem do usuário. Campo `text` conforme o contrato original."""
    text: str


@dataclass
class TextDelta:
    """Fragmento de texto emitido durante o streaming."""
    content: str


@dataclass
class StreamDone:
    """Sentinela de fim de stream."""
    pass


class LlmChatError(RuntimeError):
    """Falha de configuração ou de chamada ao provedor."""


@dataclass
class LlmChat:
    api_key: str = ""
    session_id: str = ""
    system_message: str = ""
    provider: Optional[str] = field(default=None, init=False)
    model: Optional[str] = field(default=None, init=False)

    def with_model(self, provider: str, model: str) -> "LlmChat":
        """Seleciona provedor e modelo. Retorna self para encadeamento."""
        self.provider = provider
        self.model = model
        return self

    def _resolve_key(self, env_var: str) -> str:
        key = (os.environ.get(env_var) or "").strip() or (self.api_key or "").strip()
        if not key:
            raise LlmChatError(
                f"Credencial ausente para o provedor '{self.provider}'. "
                f"Defina {env_var} no ambiente do backend."
            )
        return key

    async def stream_message(self, message: UserMessage) -> AsyncIterator[object]:
        """Emite TextDelta por fragmento e encerra com StreamDone."""
        if not self.provider or not self.model:
            raise LlmChatError("Modelo não selecionado — chame .with_model(provider, model) antes.")

        if self.provider == "anthropic":
            async for ev in self._stream_anthropic(message):
                yield ev
        elif self.provider == "openai":
            async for ev in self._stream_openai(message):
                yield ev
        else:
            raise LlmChatError(f"Provedor não suportado: {self.provider}")

        yield StreamDone()

    async def _stream_anthropic(self, message: UserMessage) -> AsyncIterator[TextDelta]:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self._resolve_key("ANTHROPIC_API_KEY"))
        # Sem `thinking`: geração de copy publicitária não exige raciocínio
        # extendido, e o produto vende a resposta aparecendo token a token —
        # thinking atrasaria o primeiro fragmento visível na tela.
        async with client.messages.stream(
            model=self.model,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=self.system_message or None,
            messages=[{"role": "user", "content": message.text}],
        ) as stream:
            async for chunk in stream.text_stream:
                if chunk:
                    yield TextDelta(content=chunk)

    async def _stream_openai(self, message: UserMessage) -> AsyncIterator[TextDelta]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._resolve_key("OPENAI_API_KEY"))
        messages = []
        if self.system_message:
            messages.append({"role": "system", "content": self.system_message})
        messages.append({"role": "user", "content": message.text})

        stream = await client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=MAX_OUTPUT_TOKENS,
            stream=True,
        )
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            text = getattr(delta, "content", None)
            if text:
                yield TextDelta(content=text)
