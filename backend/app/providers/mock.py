"""Deterministic synthetic footage. Every record is labelled synthetic."""

from __future__ import annotations

from typing import Any

from app.providers.base import ProviderError

SYNTHETIC_NOTE = "SYNTHETIC FIXTURE — not from the VAST archive."


def _hit(
    segment: str,
    parent: str,
    camera: str,
    location: str,
    start: float,
    end: float,
    observation: str,
    labels: list[str],
    score: float,
) -> dict[str, Any]:
    return {
        "source_video_id": parent,
        "source_segment_id": segment,
        "camera_id": camera,
        "location": location,
        "start_seconds": start,
        "end_seconds": end,
        "observation": f"{SYNTHETIC_NOTE} {observation}",
        "object_labels": labels,
        "source_description": f"{SYNTHETIC_NOTE} {observation}",
        "retrieval_score": score,
        "evidence_type": "synthetic_fixture",
        "filename": segment.rsplit("/", 1)[-1],
        "metadata": {
            "provider": "mock",
            "synthetic": True,
            "capture_type": "warehouse",
            "score_meaning": "fixture_rank",
        },
    }


LIBRARY = [
    _hit(
        "mock://segments/warehouse-parent-a-seg-1",
        "mock://parents/warehouse-parent-a",
        "sdg_warehouse_cam-2",
        "warehouse3",
        0.0,
        5.0,
        "A person stands beside a blue forklift that remains stationary.",
        ["person", "forklift"],
        0.91,
    ),
    _hit(
        "mock://segments/warehouse-parent-a-seg-2",
        "mock://parents/warehouse-parent-a",
        "sdg_warehouse_cam-2",
        "warehouse3",
        5.0,
        10.0,
        "The forklift begins moving and the person walks away along the aisle.",
        ["person", "forklift"],
        0.74,
    ),
    _hit(
        "mock://segments/street-parent-b-seg-1",
        "mock://parents/street-parent-b",
        "neighborhood_cam-1",
        "neighborhood",
        12.0,
        17.0,
        "A truck is stationary on a residential street. No person is visible.",
        ["truck"],
        0.88,
    ),
]


class MockVideoProvider:
    name = "mock"
    synthetic = True

    async def health(self) -> dict[str, Any]:
        return {
            "authenticated": False,
            "username": None,
            "detail": "Mock provider is active. Results are synthetic fixtures.",
        }

    async def list_catalog(self) -> dict[str, Any]:
        return {
            "provider": "mock",
            "synthetic": True,
            "overview": {"indexed_clips": len(LIBRARY), "unique_videos": 2},
            "cameras": [
                {"id": "sdg_warehouse_cam-2", "count": 2},
                {"id": "neighborhood_cam-1", "count": 1},
            ],
            "locations": [
                {"id": "warehouse3", "count": 2},
                {"id": "neighborhood", "count": 1},
            ],
            "capture_types": [{"id": "warehouse", "count": 2}],
            "videos": [
                {
                    "id": "mock://parents/warehouse-parent-a",
                    "provider": "mock",
                    "camera_id": "sdg_warehouse_cam-2",
                    "location": "warehouse3",
                    "title": "synthetic warehouse parent A",
                    "duration_seconds": 10.0,
                    "capture_start_time": None,
                    "playback_url": None,
                    "metadata": {"synthetic": True},
                }
            ],
        }

    async def search(
        self,
        query: str,
        metadata_filters: dict[str, str] | None = None,
        top_k: int = 8,
        min_similarity: float = 0.2,
    ) -> dict[str, Any]:
        filters = metadata_filters or {}
        if filters.get("camera_id") == "no-camera":
            return {"hits": [], "synthesis": None, "model": None}
        hits = []
        for hit in LIBRARY:
            if filters.get("camera_id") and hit["camera_id"] != filters["camera_id"]:
                continue
            if filters.get("location") and hit["location"] != filters["location"]:
                continue
            if filters.get("capture_type") and hit["metadata"]["capture_type"] != filters["capture_type"]:
                continue
            if hit["retrieval_score"] < min_similarity:
                continue
            hits.append(dict(hit))
        hits.sort(key=lambda item: item["retrieval_score"], reverse=True)
        return {"hits": hits[:top_k], "synthesis": None, "model": None}

    async def list_segments(self, original_video: str) -> list[dict[str, Any]]:
        return [dict(hit) for hit in LIBRARY if hit["source_video_id"] == original_video]

    async def media_url(self, source: str) -> str:
        raise ProviderError(
            "Synthetic fixtures have no playable footage. Switch VIDEO_PROVIDER to vast for archive playback.",
            status_code=404,
        )

    async def close(self) -> None:
        return None
