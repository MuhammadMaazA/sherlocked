#!/usr/bin/env python3
"""Print which required environment names are set. Never prints values."""

from __future__ import annotations

import os

NAMES = [
    "USERNAME",
    "INGRESS_URL",
    "PIPELINE",
    "S3_ENDPOINT",
    "S3_CHUNKS_BUCKET",
    "S3_SEGMENTS_BUCKET",
    "VASTDB_BUCKET",
    "VDB_SCHEMA",
    "VDB_COLLECTION",
    "WANDB_TEAM",
    "WANDB_PROJECT",
    "WANDB_API_KEY",
    "COSMOS3_REASON_URL",
    "COSMOS_EMBED1_URL",
    "YOLO_URL",
]

def main() -> None:
    for name in NAMES:
        state = "set" if os.getenv(name) else "missing"
        print(f"{name}: {state}")

if __name__ == "__main__":
    main()
