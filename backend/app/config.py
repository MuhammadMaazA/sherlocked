"""Runtime configuration. Values come from the environment, never from the repo."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def video_provider_name() -> str:
    return os.getenv("VIDEO_PROVIDER", "vast").strip().lower()


def reasoning_provider_name() -> str:
    return os.getenv("REASONING_PROVIDER", "wandb").strip().lower()


def database_path() -> Path:
    raw = os.getenv("SHERLOCKED_DB", str(ROOT / "data" / "sherlocked.db"))
    return Path(raw)


def frontend_dist() -> Path:
    return ROOT / "frontend" / "dist"


def vss_settings() -> dict[str, str]:
    return {
        "base_url": (os.getenv("VSS_URL") or os.getenv("INGRESS_URL") or "").rstrip("/"),
        "username": os.getenv("VSS_USERNAME") or os.getenv("USERNAME") or "",
        "password": os.getenv("VSS_PASSWORD") or os.getenv("PASSWORD") or "",
    }


def wandb_settings() -> dict[str, str]:
    return {
        "api_key": os.getenv("WANDB_API_KEY") or "",
        "team": os.getenv("WANDB_TEAM") or "",
        "project": os.getenv("WANDB_PROJECT") or "",
        "model": os.getenv("WANDB_MODEL") or "meta-llama/Llama-3.1-8B-Instruct",
        "base_url": os.getenv("WANDB_BASE_URL") or "https://api.inference.wandb.ai/v1",
    }
