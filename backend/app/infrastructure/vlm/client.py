"""Talks to the local model server through its OpenAI-compatible endpoint."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx

from app.domain.ports.vision_extractor import VisionExtractionError

_MAX_OUTPUT_TOKENS = 200
_MAX_VALUE_LENGTH = 160


def clean_values(raw: str, keys: tuple[str, ...]) -> dict[str, str | None]:
    """Keep only the requested keys. Never logs ``raw``: it holds what the card says."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VisionExtractionError("invalid_json") from exc
    if not isinstance(parsed, dict):
        raise VisionExtractionError("invalid_json")
    values: dict[str, str | None] = {}
    for key in keys:
        value = parsed.get(key)
        text = value.strip() if isinstance(value, str) else ""
        # El modelo a veces escribe la palabra null en lugar del valor nulo.
        if text.casefold() == "null":
            text = ""
        # Un texto largo no es un campo de licencia: es el modelo divagando.
        values[key] = text if text and len(text) <= _MAX_VALUE_LENGTH else None
    return values


class LlamaServerExtractor:
    def __init__(self, base_url: str, *, timeout_seconds: float) -> None:
        self._base_url = base_url
        self._timeout = timeout_seconds

    async def is_ready(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                response = await client.get(f"{self._base_url}/health")
        except httpx.HTTPError:
            return False
        return response.status_code == httpx.codes.OK

    async def extract(
        self,
        image: Path,
        *,
        prompt: str,
        response_format: Mapping[str, Any],
        keys: tuple[str, ...],
    ) -> dict[str, str | None]:
        encoded = base64.b64encode(image.read_bytes()).decode()
        body = {
            "model": "HYVL",
            "temperature": 0,
            "top_p": 1,
            "max_tokens": _MAX_OUTPUT_TOKENS,
            # Conservar la imagen entre licencias no acelera nada y la deja en memoria.
            "cache_prompt": False,
            "response_format": response_format,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/v1/chat/completions", json=body)
        response.raise_for_status()
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise VisionExtractionError("invalid_response") from exc
        return clean_values(content, keys)
