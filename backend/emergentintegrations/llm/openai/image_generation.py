"""Geração de imagens — implementação nativa sobre o SDK oficial `openai`.

Substitui `emergentintegrations.llm.openai.image_generation` preservando o
contrato consumido por `server.py`: `generate_images(...)` devolve uma lista de
imagens já decodificadas em bytes.
"""

import base64
import os
from dataclasses import dataclass
from typing import List


class ImageGenerationError(RuntimeError):
    """Falha de configuração ou de chamada ao provedor de imagens."""


@dataclass
class OpenAIImageGeneration:
    api_key: str = ""

    def _resolve_key(self) -> str:
        key = (os.environ.get("OPENAI_API_KEY") or "").strip() or (self.api_key or "").strip()
        if not key:
            raise ImageGenerationError(
                "Credencial ausente para geração de imagem. "
                "Defina OPENAI_API_KEY no ambiente do backend."
            )
        return key

    async def generate_images(
        self,
        prompt: str,
        model: str = "gpt-image-1",
        number_of_images: int = 1,
        quality: str = "medium",
        size: str = "1024x1024",
    ) -> List[bytes]:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._resolve_key())
        resp = await client.images.generate(
            model=model,
            prompt=prompt,
            n=number_of_images,
            quality=quality,
            size=size,
        )

        images: List[bytes] = []
        for item in resp.data or []:
            b64 = getattr(item, "b64_json", None)
            if b64:
                images.append(base64.b64decode(b64))

        if not images:
            raise ImageGenerationError("O provedor não devolveu nenhuma imagem.")
        return images
