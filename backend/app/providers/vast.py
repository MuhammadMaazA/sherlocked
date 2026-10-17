"""VAST Video Search & Summary provider.

Talks to the team's already-deployed retrieval API. Credentials stay in the
process environment and are never returned to the browser.
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import quote

import httpx

from app.config import vss_settings
from app.providers.base import ProviderError


def parse_labels(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text or text == "[]":
            return []
        if text.startswith("["):
            try:
                return parse_labels(json.loads(text))
            except json.JSONDecodeError:
                pass
        return [part.strip() for part in text.split(",") if part.strip()]
    return []


def normalize_search_hit(row: dict[str, Any]) -> dict[str, Any]:
    """Map a VSS segment hit into a Sherlocked evidence payload without an id."""
    observation = (row.get("reasoning_content") or "").strip()
    labels = parse_labels(row.get("object_classes"))
    filename = row.get("filename") or ""
    parent = row.get("original_video") or ""
    parent_name = parent.rsplit("/", 1)[-1] if parent else None
    metadata: dict[str, Any] = {
        "provider": "vast",
        "synthetic": False,
        "capture_type": row.get("capture_type"),
        "cosmos_model": row.get("cosmos_model"),
        "score_meaning": "hybrid_similarity",
        "parent_filename": parent_name,
        "segment_number": row.get("segment_number"),
        "total_segments": row.get("total_segments"),
        "indexed_at": row.get("upload_timestamp"),
        "indexed_at_meaning": "Pipeline ingest time, not a verified capture clock.",
        "perception_source": row.get("perception_source"),
        "max_detection_conf": row.get("max_detection_conf"),
        "detection_count": row.get("detection_count"),
    }
    return {
        "source_video_id": parent or None,
        "source_segment_id": row.get("source"),
        "camera_id": row.get("camera_id"),
        "location": row.get("location"),
        "start_seconds": row.get("segment_start_sec"),
        "end_seconds": row.get("segment_end_sec"),
        "observation": observation,
        "object_labels": labels,
        "source_description": observation,
        "retrieval_score": row.get("similarity_score"),
        "evidence_type": "model_caption",
        "filename": filename or None,
        "metadata": {key: value for key, value in metadata.items() if value is not None},
    }


class VastVideoProvider:
    name = "vast"
    synthetic = False

    def __init__(self) -> None:
        settings = vss_settings()
        self.base_url = settings["base_url"]
        self.username = settings["username"]
        self.password = settings["password"]
        self._token: str | None = None
        self._token_at = 0.0
        self._client: httpx.AsyncClient | None = None
        self._catalog: dict[str, Any] | None = None
        self._catalog_at = 0.0

    async def _client_get(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(70.0, connect=10.0))
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _login(self) -> str:
        if not self.base_url or not self.username or not self.password:
            raise ProviderError("VSS URL or credentials are not configured on this host.", status_code=503)
        client = await self._client_get()
        response = await client.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"username": self.username, "password": self.password},
        )
        if response.status_code != 200:
            raise ProviderError("VSS authentication failed.", status_code=502)
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise ProviderError("VSS authentication returned no token.", status_code=502)
        self._token = token
        self._token_at = time.time()
        return token

    async def token(self) -> str:
        if self._token and (time.time() - self._token_at) < 20 * 60:
            return self._token
        return await self._login()

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict | None = None,
        params: dict | None = None,
        retry: bool = True,
    ) -> Any:
        client = await self._client_get()
        headers = {"Authorization": f"Bearer {await self.token()}"}
        response = await client.request(
            method,
            f"{self.base_url}{path}",
            json=json_body,
            params=params,
            headers=headers,
        )
        if response.status_code == 401 and retry:
            self._token = None
            return await self._request(method, path, json_body, params, retry=False)
        if response.status_code >= 400:
            detail = response.text[:240].replace("\n", " ")
            code = 502 if response.status_code >= 500 else response.status_code
            raise ProviderError(f"VSS {path} returned {response.status_code}: {detail}", status_code=code)
        if not response.content:
            return {}
        return response.json()

    async def health(self) -> dict[str, Any]:
        me = await self._request("GET", "/api/v1/auth/me")
        return {
            "authenticated": True,
            "username": me.get("username"),
            "auth_type": me.get("auth_type"),
        }

    async def list_catalog(self) -> dict[str, Any]:
        if self._catalog and (time.time() - self._catalog_at) < 120:
            return self._catalog
        stats = await self._request("GET", "/api/v1/dashboard/stats", params={"scope": "all"})
        explore = await self._request(
            "GET",
            "/api/v1/videos/explore",
            params={"scope": "all", "limit": 12, "offset": 0},
        )
        metadata = stats.get("metadata") or {}

        def pairs(key: str) -> list[dict[str, Any]]:
            rows = metadata.get(key) or []
            cleaned = []
            for row in rows:
                if isinstance(row, dict) and row.get("label") is not None:
                    cleaned.append({"id": row.get("label"), "count": row.get("count")})
            return cleaned

        videos = []
        for chunk in explore.get("chunks") or []:
            parent = chunk.get("original_video") or ""
            videos.append(
                {
                    "id": parent,
                    "provider": "vast",
                    "camera_id": chunk.get("camera_id"),
                    "location": chunk.get("location"),
                    "title": chunk.get("filename") or parent.rsplit("/", 1)[-1],
                    "duration_seconds": chunk.get("chunk_duration_sec"),
                    "capture_start_time": None,
                    "playback_url": None,
                    "metadata": {
                        "capture_type": chunk.get("capture_type"),
                        "indexed_at": chunk.get("upload_timestamp"),
                        "indexed_at_meaning": "Pipeline ingest time, not a verified capture clock.",
                        "preview_caption": (chunk.get("reasoning_content") or "")[:280],
                    },
                }
            )
        overview = stats.get("overview") or {}
        alignment = stats.get("pipeline_alignment") or {}
        catalog = {
            "provider": "vast",
            "synthetic": False,
            "overview": {
                "indexed_clips": overview.get("indexed_clips"),
                "unique_videos": overview.get("unique_videos"),
                "fully_indexed_videos": overview.get("fully_indexed_videos"),
                "pipeline_healthy": alignment.get("healthy"),
            },
            "cameras": pairs("camera_id"),
            "locations": pairs("location"),
            "capture_types": pairs("capture_type"),
            "objects": (stats.get("objects") or [])[:12],
            "videos": videos,
        }
        self._catalog = catalog
        self._catalog_at = time.time()
        return catalog

    async def search(
        self,
        query: str,
        metadata_filters: dict[str, str] | None = None,
        top_k: int = 8,
        min_similarity: float = 0.2,
    ) -> dict[str, Any]:
        body = {
            "query": query,
            "top_k": top_k,
            "llm_top_n": 1,
            "min_similarity": min_similarity,
            "time_filter": "all",
            "metadata_filters": metadata_filters or {},
            "include_public": True,
        }
        payload = await self._request("POST", "/api/v1/search", json_body=body)
        hits = [normalize_search_hit(row) for row in payload.get("results") or [] if isinstance(row, dict)]
        synthesis = payload.get("llm_synthesis") or {}
        text = synthesis.get("response") if isinstance(synthesis, dict) else None
        model = synthesis.get("model") if isinstance(synthesis, dict) else None
        return {"hits": hits, "synthesis": text, "model": model}

    async def list_segments(self, original_video: str) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/api/v1/tools/segments", params={"original_video": original_video})
        return [normalize_search_hit(row) for row in payload.get("segments") or [] if isinstance(row, dict)]

    async def detections(self, source: str) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/videos/detections", params={"source": source})

    async def media_url(self, source: str) -> str:
        if not source:
            raise ProviderError("This evidence item has no source URI.", status_code=404)
        token = await self.token()
        return (
            f"{self.base_url}/api/v1/videos/stream"
            f"?source={quote(source, safe='')}"
            f"&token={quote(token, safe='._-')}"
        )
