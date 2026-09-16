"""Camada de compatibilidade nativa da Vanguarda.IA.

Reimplementa a superfície da SDK proprietária `emergentintegrations` sobre os
SDKs oficiais `anthropic` e `openai`, de modo que `server.py` rode sem qualquer
dependência da plataforma Emergent. O contrato público é idêntico ao original:

    LlmChat(api_key=..., session_id=..., system_message=...)
        .with_model(provider, model)
        .stream_message(UserMessage(text=...))  -> TextDelta... StreamDone

    OpenAIImageGeneration(api_key=...).generate_images(...) -> list[bytes]
"""

__all__ = ["llm"]
