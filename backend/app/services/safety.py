"""Indexed warehouse replay for Safety Command.

Classifications come from stored Cosmos captions. A semantic-search score never
promotes a clip to an incident. Alerts use the segment window, not a guessed frame.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.providers.base import ProviderError
from app.providers.reasoning import parse_json_object

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "wall.json"

CONTACT_PHRASES = ("makes contact", "made contact", "collides", "collision", "struck", "strikes the")
CLIMB_PHRASES = ("climbs onto", "climbs into", "climb onto", "climbs on")
BANNED_CLAIMS = ("employee id", "injured", "injury", "fatality", "fatal", "guilty", "named worker", "root cause")


def classify_text(text: str, labels: list[str] | None = None) -> str:
    """Map one stored caption plus YOLO labels to a safety category.

    Search relevance is not an input. The camera code is not an input.
    """
    return assess_window(text, labels or [])["category"]


def assess_window(text: str, labels: list[str] | None = None) -> dict[str, Any]:
    """Score one indexed window from the Cosmos caption and YOLO classes."""
    lowered = (text or "").lower()
    label_set = {str(label).lower() for label in (labels or [])}
    has_person = "person" in lowered or "person" in label_set
    has_forklift = "forklift" in lowered
    signals: list[str] = []
    if "person" in label_set:
        signals.append("YOLO11 recorded a person in this window.")
    elif has_person:
        signals.append("Cosmos caption mentions a person. YOLO11 did not store a person class here.")

    if any(phrase in lowered for phrase in CONTACT_PHRASES):
        signals.insert(0, "Cosmos3-Reason caption says the person makes contact with the forklift.")
        category = "contact"
    elif any(phrase in lowered for phrase in CLIMB_PHRASES):
        signals.insert(0, "Cosmos3-Reason caption says the person climbs onto the forklift.")
        category = "other_safety_concern"
    elif "safe distance" in lowered:
        signals.insert(0, "Cosmos3-Reason caption says the person keeps a safe distance.")
        category = "routine"
    elif has_forklift and ("not clear" in lowered or "off-screen" in lowered) and ("run" in lowered or "quickly" in lowered):
        signals.insert(0, "Cosmos3-Reason caption describes quick movement beside the forklift and does not give a cause.")
        category = "potential_near_miss"
    elif has_person and has_forklift and any(
        phrase in lowered for phrase in ("moving forward", "moves forward", "begins to move forward", "moves slowly")
    ):
        signals.insert(0, "Cosmos3-Reason caption describes forklift motion while a person is in the scene.")
        category = "potential_near_miss"
    elif has_person and has_forklift and "toward the forklift" in lowered:
        signals.insert(0, "Cosmos3-Reason caption describes a person moving toward the forklift. No contact is stated.")
        category = "watch"
    else:
        if has_forklift:
            signals.append("Cosmos3-Reason caption describes ordinary aisle activity.")
        category = "routine"
    return {"category": category, "signals": signals}


def _headline(category: str) -> str | None:
    if category == "contact":
        return "Person–forklift contact"
    if category == "other_safety_concern":
        return "Person climbs onto forklift"
    if category == "potential_near_miss":
        return "Person and moving forklift"
    if category == "watch":
        return "Person moves toward forklift"
    return None


def _ticker(text: str) -> str:
    sentence = (text or "").replace("\n", " ").strip()
    for mark in (". ", "? ", "! "):
        if mark in sentence:
            sentence = sentence.split(mark, 1)[0] + mark.strip()
            break
    if len(sentence) > 140:
        sentence = sentence[:137].rstrip() + "…"
    return sentence


def _labels_for_display(labels: list[str], observation: str) -> list[str]:
    """Keep caption-supported equipment words and the person class. Drop COCO misfires."""
    shown: list[str] = []
    if "person" in {label.lower() for label in labels} or "person" in observation.lower():
        shown.append("person")
    if "forklift" in observation.lower():
        shown.append("forklift")
    return shown


def load_wall() -> dict[str, Any]:
    raw = json.loads(DATA_PATH.read_text())
    cameras = []
    for camera in raw["cameras"]:
        segments = []
        takeover = None
        for segment in camera["segments"]:
            observation = (segment.get("observation") or "").strip()
            assessed = assess_window(observation, segment.get("labels") or [])
            category = assessed["category"]
            entry = {
                "start": segment.get("start"),
                "end": segment.get("end"),
                "category": category,
                "headline": _headline(category),
                "ticker": _ticker(observation),
                "observation": observation,
                "signals": assessed["signals"],
                "labels": segment.get("labels") or [],
                "display_labels": _labels_for_display(segment.get("labels") or [], observation),
                "filename": segment.get("filename"),
                "takeover": category == "contact",
            }
            segments.append(entry)
            if entry["takeover"] and takeover is None:
                takeover = {
                    "start": entry["start"],
                    "end": entry["end"],
                    "headline": entry["headline"],
                    "category": category,
                    "filename": entry["filename"],
                }
        cameras.append(
            {
                "code": camera["code"],
                "camera_id": camera.get("camera_id"),
                "location": camera.get("location"),
                "parent_name": (camera.get("parent") or "").rsplit("/", 1)[-1],
                "segments": segments,
                "takeover": takeover,
            }
        )
    cameras.sort(key=lambda item: item["code"])
    flagged = [item["code"] for item in cameras if _flagged(item)]
    return {
        "mode": "indexed_footage_replay",
        "title": "Safety Command",
        "archive_camera": raw.get("source"),
        "disclaimer": (
            "Each window is scored from its Cosmos3-Reason caption and YOLO11 classes. "
            "The camera name is not a rule. A file uploaded to VAST is segmented, detected, "
            "described, and embedded by that pipeline; the same score applies after it is indexed. "
            "This screen replays indexed footage. It does not run a new model on the pixels."
        ),
        "engines": [
            {"name": "VAST", "role": "Video, vectors, playback"},
            {"name": "Cosmos Reason", "role": "Segment captions"},
            {"name": "Cosmos Embed", "role": "Search vectors"},
            {"name": "YOLO11", "role": "Person boxes"},
            {"name": "W&B", "role": "Safety note"},
        ],
        "feeds": len(cameras),
        "events_flagged": len(flagged),
        "flagged_cameras": flagged,
        "cameras": cameras,
    }


def _flagged(camera: dict[str, Any]) -> bool:
    return any(
        segment["category"] in {"contact", "other_safety_concern", "potential_near_miss"}
        for segment in camera["segments"]
    )


def camera_by_code(code: str) -> dict[str, Any] | None:
    wall = load_wall()
    for camera in wall["cameras"]:
        if camera["code"] == code:
            return camera
    return None


def parent_source(code: str) -> str | None:
    raw = json.loads(DATA_PATH.read_text())
    for camera in raw["cameras"]:
        if camera["code"] == code:
            return camera.get("parent")
    return None


def alert_segment_source(code: str) -> tuple[dict[str, Any], str] | None:
    public = camera_by_code(code)
    if not public:
        return None
    target_start = public["takeover"]["start"] if public.get("takeover") else None
    if target_start is None:
        for segment in public["segments"]:
            if segment["category"] != "routine":
                target_start = segment["start"]
                break
    if target_start is None:
        return None
    raw = json.loads(DATA_PATH.read_text())
    for camera in raw["cameras"]:
        if camera["code"] != code:
            continue
        for segment in camera["segments"]:
            if segment.get("start") == target_start:
                return {"start": segment.get("start"), "end": segment.get("end")}, segment.get("source")
    return None


def investigation(code: str) -> dict[str, Any] | None:
    camera = camera_by_code(code)
    if not camera:
        return None
    focus = None
    for segment in camera["segments"]:
        if segment["category"] != "routine":
            focus = segment
            break
    focus = focus or (camera["segments"][-1] if camera["segments"] else None)
    if not focus:
        return None
    category = focus["category"]
    hypotheses = []
    uncertain = [
        "The person is not identified. Worker A is a label for this clip only and is not matched to any other recording.",
        "These files are separate synthetic renders that share a camera id. They are not one continuous multi-camera incident.",
        "YOLO COCO classes do not include forklift. A stored class such as boat, truck, or suitcase is not treated as that object.",
    ]
    if category == "contact":
        hypotheses.append(
            {
                "text": "The caption places a person and a forklift in the same floor area and says the person makes contact with the forklift.",
                "status": "supported_by_caption",
            }
        )
        hypotheses.append(
            {
                "text": "Separation distance is not measured. Insufficient separation is a hypothesis, not a measured finding.",
                "status": "hypothesis",
            }
        )
        uncertain.append("The caption does not say the forklift struck the person, and it does not describe an injury.")
    elif category == "other_safety_concern":
        hypotheses.append(
            {
                "text": "The caption says the person climbs onto the forklift and operates it. No contact or injury is described.",
                "status": "supported_by_caption",
            }
        )
    elif category == "potential_near_miss":
        hypotheses.append(
            {
                "text": "The stored caption puts a person and forklift motion in the same window. It does not describe contact.",
                "status": "supported_by_caption",
            }
        )
        uncertain.append("This window is not promoted to contact.")
    elif category == "watch":
        hypotheses.append(
            {
                "text": "The caption describes a person moving toward a forklift. No contact or climb is described.",
                "status": "supported_by_caption",
            }
        )
    else:
        uncertain.append("No contact, climb, or unresolved near miss is described in the stored captions for this recording.")
    raw_labels = sorted({label for segment in camera["segments"] for label in segment["labels"]})
    return {
        "camera": camera["code"],
        "camera_id": camera["camera_id"],
        "location": camera["location"],
        "parent_name": camera["parent_name"],
        "category": category,
        "headline": focus["headline"] or "Routine warehouse activity",
        "window": {"start": focus["start"], "end": focus["end"], "precision": "segment"},
        "observed": focus["observation"],
        "filename": focus["filename"],
        "display_labels": focus["display_labels"],
        "signals": focus.get("signals") or [],
        "detector_labels": raw_labels,
        "person_annotation": "Worker A — unidentified. This label applies only inside the selected clip.",
        "hypotheses": hypotheses,
        "uncertain": uncertain,
        "review": [
            "Watch the marked five-second window before treating the caption as a confirmed event.",
            "Do not infer an employee record, injury, or root cause from this render.",
        ],
        "segments": camera["segments"],
    }


def default_controls(category: str) -> list[str]:
    if category == "contact":
        return [
            "Proposed: paint a pedestrian walkway that does not cross the forklift path in this scene.",
            "Proposed: keep the forklift stopped while a person is beside it.",
            "Human review of the 5–10s window before any incident record is closed.",
        ]
    if category == "other_safety_concern":
        return [
            "Proposed: restrict climbing onto equipment to a defined mounting step.",
            "Demo training topic: boarding and leaving a forklift.",
            "Human review of whether this render shows an authorised operator. The caption does not say.",
        ]
    if category == "potential_near_miss":
        return [
            "Proposed: mark an exclusion zone beside a moving forklift.",
            "Human review. The caption says the cause of the quick movement is not clear.",
        ]
    return ["No additional control is proposed from this recording."]


def fallback_assessment(view: dict[str, Any]) -> str:
    controls = default_controls(view["category"])
    lines = [
        f"Preliminary hazard note — {view['camera']}",
        f"Recording: {view['parent_name']}",
        f"Segment: {view['filename']}",
        f"Window: {view['window']['start']}–{view['window']['end']}s (segment precision, not a single frame).",
        f"Category: {view['category']}",
        "",
        "Observed, from the indexed caption:",
        view["observed"],
        "",
        "Proposed controls (not a physical simulation):",
        *[f"- {item}" for item in controls],
        "",
        "Needs a person:",
        *[f"- {item}" for item in view["uncertain"]],
    ]
    return "\n".join(lines)


async def draft_assessment(reasoner, view: dict[str, Any]) -> dict[str, Any]:
    """Ask W&B to word a note. Reject any draft that adds claims the caption does not carry."""
    fallback = fallback_assessment(view)
    system = (
        "You write a short warehouse safety note from one indexed caption. "
        "Use only facts in the caption. Do not invent injuries, names, employee numbers, "
        "root causes, or a claim that a forklift struck a person unless the caption says that. "
        "Return JSON with keys observed (string), controls (array of short proposed measures), uncertain (array of strings)."
    )
    user = json.dumps(
        {
            "category": view["category"],
            "window_seconds": [view["window"]["start"], view["window"]["end"]],
            "caption": view["observed"],
        }
    )
    text, model = await reasoner.complete(system, user)
    parsed = parse_json_object(text or "")
    if not parsed:
        return {"body": fallback, "reasoner": "deterministic", "model": None}
    blob = json.dumps(parsed).lower()
    if any(token in blob for token in BANNED_CLAIMS):
        return {"body": fallback, "reasoner": "deterministic", "model": model}
    observed = str(parsed.get("observed") or "").strip()
    if not observed:
        return {"body": fallback, "reasoner": "deterministic", "model": model}
    controls = parsed.get("controls") if isinstance(parsed.get("controls"), list) else []
    uncertain = parsed.get("uncertain") if isinstance(parsed.get("uncertain"), list) else []
    lines = [
        f"Preliminary hazard note — {view['camera']}",
        f"Recording: {view['parent_name']}",
        f"Segment: {view['filename']}",
        f"Window: {view['window']['start']}–{view['window']['end']}s (segment precision).",
        f"Category: {view['category']}",
        "",
        "Observed:",
        observed,
        "",
        "Indexed caption:",
        view["observed"],
        "",
        "Proposed controls:",
        *[f"- {item}" for item in controls if isinstance(item, str)],
        "",
        "Needs a person:",
        *[f"- {item}" for item in uncertain if isinstance(item, str)],
        "",
        "Wording model: " + (model or "wandb") + ". The category was assigned from the caption before this draft.",
    ]
    return {"body": "\n".join(lines), "reasoner": "wandb", "model": model}


def training_task(view: dict[str, Any]) -> dict[str, str]:
    if view["category"] == "contact":
        title = "Demo induction: person and forklift in the same aisle"
    elif view["category"] == "other_safety_concern":
        title = "Demo induction: boarding a forklift"
    else:
        title = "Demo induction: working near a forklift"
    body = (
        f"{title}. Queued for a safety officer to review. "
        "This demo queue does not notify a person and is not tied to an employee record. "
        f"Source {view['camera']} {view['filename']}."
    )
    return {"title": title, "body": body}


def downsample_detections(payload: dict[str, Any], segment_start: float) -> dict[str, Any]:
    """Normalize person boxes onto the parent timeline. Other COCO classes are omitted."""
    shape = payload.get("video_shape") or [1080, 1920]
    height = float(shape[0] or 1080)
    width = float(shape[1] or 1920)
    frames_out = []
    last = -1.0
    for frame in payload.get("frames") or []:
        local = float(frame.get("time_sec") or 0)
        if local - last < 0.2 and frames_out:
            continue
        frame_shape = frame.get("shape") or shape
        frame_h = float(frame_shape[0] or height)
        frame_w = float(frame_shape[1] or width)
        boxes = []
        for detection in frame.get("detections") or []:
            if str(detection.get("label") or "").lower() != "person":
                continue
            confidence = float(detection.get("confidence") or 0)
            if confidence < 0.45:
                continue
            bbox = detection.get("bbox") or []
            if len(bbox) != 4:
                continue
            x1, y1, x2, y2 = [float(value) for value in bbox]
            if frame_w <= 0 or frame_h <= 0:
                continue
            boxes.append(
                {
                    "label": "person",
                    "confidence": round(confidence, 3),
                    "x": x1 / frame_w,
                    "y": y1 / frame_h,
                    "w": (x2 - x1) / frame_w,
                    "h": (y2 - y1) / frame_h,
                }
            )
        if not boxes:
            continue
        last = local
        frames_out.append({"time_sec": round(segment_start + local, 3), "boxes": boxes})
    return {
        "video_shape": [int(height), int(width)],
        "frames": frames_out,
        "note": "Person boxes from the stored YOLO sidecar, timed from the start of the parent recording. Other detector classes are omitted.",
    }


def render_safety_html(view: dict[str, Any], actions: list[dict[str, Any]]) -> str:
    def block(text: str) -> str:
        return "<br>".join(
            (line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")) for line in text.splitlines()
        )

    action_html = "".join(
        f"<article><p class='k'>{item['kind']} · {item['status']}</p><h3>{block(item['title'])}</h3><p>{block(item['body'])}</p></article>"
        for item in actions
    ) or "<p>No response has been saved yet.</p>"
    factors = "".join(f"<li>{block(item['text'])} <em>({item['status']})</em></li>" for item in view["hypotheses"])
    gaps = "".join(f"<li>{block(item)}</li>" for item in view["uncertain"])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Safety note {view['camera']}</title>
<style>
body {{ margin: 0; background: #121416; color: #f2f4f6; font: 15px/1.45 "IBM Plex Sans", sans-serif; }}
main {{ max-width: 820px; margin: 0 auto; padding: 32px 20px 64px; }}
h1 {{ font-size: 28px; letter-spacing: 0.08em; margin-bottom: 0; }}
.k {{ color: #f5c400; letter-spacing: 0.14em; text-transform: uppercase; font-size: 12px; }}
article {{ border: 1px solid #2c3136; padding: 12px 14px; margin: 10px 0; }}
em {{ color: #9aa3ab; }}
</style></head><body><main>
<p class="k">Sherlocked · indexed footage replay</p>
<h1>{view['camera']} · {block(view['headline'])}</h1>
<p>{view['parent_name']}<br>Segment {view['filename']}<br>Window {view['window']['start']}–{view['window']['end']} seconds. Segment precision, not a single frame.</p>
<h2>Observed</h2>
<p>{block(view['observed'])}</p>
<h2>Factors</h2>
<ul>{factors or '<li>None proposed.</li>'}</ul>
<h2>Unresolved</h2>
<ul>{gaps}</ul>
<h2>Saved responses</h2>
{action_html}
<p class="k">Worker A is unidentified and is not an employee record. Proposed controls are not a physical simulation.</p>
</main></body></html>"""


async def detections_for(provider, code: str) -> dict[str, Any]:
    located = alert_segment_source(code)
    if not located:
        return {"frames": [], "note": "No non-routine segment to overlay."}
    window, source = located
    if not source or not hasattr(provider, "detections"):
        return {"frames": [], "note": "Detections are unavailable for this provider."}
    try:
        payload = await provider.detections(source)
    except ProviderError:
        return {"frames": [], "note": "No YOLO sidecar for this segment."}
    if not isinstance(payload, dict):
        return {"frames": [], "note": "Detections response was empty."}
    result = downsample_detections(payload, float(window["start"] or 0))
    result["window"] = window
    return result
