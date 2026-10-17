"""Weights & Biases serverless inference for structured investigation text.

The model may only cite evidence ids the retriever already returned. If it
does not respond with usable JSON, callers keep the deterministic findings.
"""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import wandb_settings


def parse_json_object(text: str) -> dict[str, Any] | None:
    raw = text.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            parsed = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


class NullReasoner:
    name = "deterministic"

    async def complete(self, system: str, user: str) -> tuple[str | None, str | None]:
        return None, None

    async def close(self) -> None:
        return None


class WandbReasoner:
    name = "wandb"

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _client_get(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(35.0, connect=10.0))
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def complete(self, system: str, user: str) -> tuple[str | None, str | None]:
        settings = wandb_settings()
        if not settings["api_key"]:
            return None, None
        headers = {
            "Authorization": f"Bearer {settings['api_key']}",
            "Content-Type": "application/json",
        }
        if settings["team"] and settings["project"]:
            headers["OpenAI-Project"] = f"{settings['team']}/{settings['project']}"
        body = {
            "model": settings["model"],
            "temperature": 0.1,
            "max_tokens": 1400,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        try:
            client = await self._client_get()
            response = await client.post(f"{settings['base_url']}/chat/completions", headers=headers, json=body)
        except httpx.HTTPError:
            return None, None
        if response.status_code >= 400:
            return None, None
        payload = response.json()
        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return None, None
        model = payload.get("model") or settings["model"]
        return text, model
