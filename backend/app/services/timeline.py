"""Group observations by parent recording.

Offsets are seconds inside that parent. Different parents are not placed on
one wall clock, even when they share a camera id.
"""

from __future__ import annotations

from typing import Any


CLOCK_NOTE = (
    "Times are offsets inside this parent recording. "
    "This group is not aligned to other recordings."
)


def build_timeline(case_id: str | None, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for item in evidence:
        parent = item.get("source_video_id") or item.get("id")
        group = groups.get(parent)
        if group is None:
            label = (item.get("metadata") or {}).get("parent_filename") or item.get("filename") or "Recording"
            group = {
                "group_id": parent,
                "camera_id": item.get("camera_id"),
                "location": item.get("location"),
                "label": label,
                "clock": "relative_to_parent",
                "clock_note": CLOCK_NOTE,
                "events": [],
            }
            groups[parent] = group
        start = item.get("start_seconds")
        event_id = f"evt_{item['id']}"
        group["events"].append(
            {
                "id": event_id,
                "case_id": case_id,
                "description": item.get("observation") or "",
                "event_type": "observation",
                "absolute_time": None,
                "relative_time": start,
                "end_seconds": item.get("end_seconds"),
                "evidence_ids": [item["id"]],
                "verification_status": "observed",
            }
        )
    ordered = list(groups.values())
    for group in ordered:
        group["events"].sort(key=lambda event: (event["relative_time"] is None, event["relative_time"] or 0))
    ordered.sort(key=lambda group: (group.get("camera_id") or "", group.get("label") or ""))
    note = (
        "Each band is one parent recording. Bands are not synchronised to a shared clock."
        if len(ordered) > 1
        else "Offsets are relative to the parent recording."
    )
    return {"groups": ordered, "note": note}
