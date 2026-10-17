"""Video provider interface."""

from __future__ import annotations

from typing import Any, Protocol


class ProviderError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class VideoProvider(Protocol):
    name: str
    synthetic: bool

    async def health(self) -> dict[str, Any]: ...

    async def list_catalog(self) -> dict[str, Any]: ...

    async def search(
        self,
        query: str,
        metadata_filters: dict[str, str] | None = None,
        top_k: int = 8,
        min_similarity: float = 0.2,
    ) -> dict[str, Any]: ...

    async def list_segments(self, original_video: str) -> list[dict[str, Any]]: ...

    async def media_url(self, source: str) -> str: ...

    async def close(self) -> None: ...
