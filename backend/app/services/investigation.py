"""Bounded investigation: search, timeline, hypotheses, contradiction check.

The retriever is the only source of observations. Language-model text is kept
only when every cited id was retrieved.
"""

from __future__ import annotations

import time
from typing import Any

from app.providers.base import ProviderError
from app.providers.reasoning import parse_json_object
from app.services.planner import contradiction_query, plan_queries
from app.services.timeline import build_timeline
from app.services.validation import bullets_citing, validate_hypotheses

MAX_SEARCHES = 5
MAX_CLIPS = 12
MAX_PARENTS = 3
SYSTEM = (
    "You are an evidence clerk for a video investigation. "
    "Use only the supplied evidence. Do not invent people, cameras, times, or events. "
    "Do not identify a person, infer criminal intent, or assign guilt. "
    "Reply with one JSON object and no markdown. "
    "Every string in observed, inferred, and uncertain must contain at least one evidence id. "
    "supporting_evidence_ids and contradicting_evidence_ids must be chosen from the supplied ids. "
    "status may be supported only when two or more supporting ids share the same parent_id. "
    "Otherwise use unverified. Use contradicted only when supplied captions conflict."
)


def _polarity(text: str) -> str:
    lowered = text.lower()
    motion = any(word in lowered for word in ("moving", "moves", "begins to move", "driving", "runs", "running", "walks away"))
    still = any(
        word in lowered
        for word in ("stationary", "remains still", "no visible movement", "stands still", "not moving", "remains stationary")
    )
    if motion and still:
        return "sequence"
    if motion:
        return "motion"
    if still:
        return "still"
    return "unclear"


def _dedupe(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for hit in hits:
        key = hit.get("source_segment_id") or hit.get("filename") or hit.get("observation")
        current = best.get(key)
        score = hit.get("retrieval_score") or 0
        if current is None or score > (current.get("retrieval_score") or 0):
            best[key] = hit
    ordered = list(best.values())
    ordered.sort(key=lambda item: item.get("retrieval_score") or 0, reverse=True)
    return ordered[:MAX_CLIPS]


def _search_plan(queries: list[str], cameras: list[str]) -> list[tuple[str, str | None]]:
    scopes = cameras[:3] or [None]
    planned: list[tuple[str, str | None]] = []
    for index, query in enumerate(queries):
        targets = scopes if index == 0 else scopes[:1]
        for camera in targets:
            planned.append((query, camera))
            if len(planned) >= MAX_SEARCHES - 1:
                return planned
    return planned


def deterministic_hypotheses(case_id: str | None, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_parent: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        by_parent.setdefault(item.get("source_video_id") or item["id"], []).append(item)
    hypotheses: list[dict[str, Any]] = []
    for index, (parent, items) in enumerate(by_parent.items(), start=1):
        items = sorted(items, key=lambda row: (row.get("start_seconds") is None, row.get("start_seconds") or 0))
        camera = items[0].get("camera_id") or "unknown camera"
        sentences = []
        for item in items[:3]:
            text = " ".join((item.get("observation") or "").split())
            sentences.append(f"{item['id']} ({item.get('start_seconds')}–{item.get('end_seconds')}s): {text[:220]}")
        status = "unverified"
        supporting = [item["id"] for item in items]
        contradicting: list[str] = []
        polarities = {item["id"]: _polarity(item.get("observation") or "") for item in items}
        motion_ids = [item_id for item_id, flag in polarities.items() if flag == "motion"]
        still_ids = [item_id for item_id, flag in polarities.items() if flag == "still"]
        questions = [
            "Do these captions describe one continuous action, or separate moments?",
            "Has a person reviewed the frames, or only the indexed caption?",
        ]
        if motion_ids and still_ids:
            status = "contradicted"
            supporting = motion_ids
            contradicting = still_ids
            statement = (
                f"On {camera}, captions inside parent recording {parent.rsplit('/', 1)[-1]} disagree about motion. "
                "One caption describes movement and another describes something stationary. "
                "That conflict is unresolved and does not prove either caption false."
            )
        elif len(items) >= 2:
            status = "supported"
            statement = (
                f"On {camera}, two or more indexed captions from the same parent recording describe a sequence. "
                + " ".join(sentences)
                + " This supports a caption sequence only. It is not identity, intent, or a shared clock with other recordings."
            )
        else:
            statement = (
                f"On {camera}, a single indexed caption is available for this parent recording. "
                + sentences[0]
                + " A single caption is not enough to reconstruct an incident."
            )
        hypotheses.append(
            {
                "id": f"hyp_{case_id or 'x'}_{index}",
                "case_id": case_id,
                "statement": statement,
                "supporting_evidence_ids": supporting,
                "contradicting_evidence_ids": contradicting,
                "unresolved_questions": questions,
                "status": status,
            }
        )
    return validate_hypotheses(hypotheses, evidence)


def deterministic_findings(evidence: list[dict[str, Any]], timeline: dict[str, Any]) -> dict[str, Any]:
    if not evidence:
        return {
            "observed": [],
            "inferred": [],
            "uncertain": ["No indexed segments matched the searches. Nothing was invented to fill the gap."],
            "next_steps": [
                "Broaden the camera or location filter.",
                "Rephrase the question around visible objects, such as a person, vehicle, or forklift.",
            ],
            "synthesis_note": None,
        }
    observed = []
    for item in evidence:
        window = f"{item.get('start_seconds')}–{item.get('end_seconds')}s"
        observed.append(
            f"{item['id']}: {item.get('camera_id') or 'camera unknown'} {window} — {item.get('observation')}"
        )
    uncertain = [
        "Indexed captions were written by a video model (Cosmos Reason via the VAST pipeline). They are not human-verified observations.",
        "Retrieval scores are hybrid similarity ranks, not calibrated probabilities.",
        timeline.get("note") or "Clip offsets are relative to each parent recording.",
        "Similar appearance across recordings is not an identification of the same person or vehicle.",
    ]
    steps = ["Open each cited segment and confirm the caption against the frames."]
    if len(timeline.get("groups") or []) > 1:
        steps.append("Review each parent recording separately. Do not treat the bands as one clock.")
    steps.append("Ask a follow-up that names a visible object or action still in question.")
    return {
        "observed": observed,
        "inferred": ["No additional inference was added beyond the hypotheses, which cite only retrieved captions."],
        "uncertain": uncertain,
        "next_steps": steps,
        "synthesis_note": None,
    }


def _plain_steps(lines: list | None) -> list[str]:
    kept: list[str] = []
    for item in lines or []:
        if not isinstance(item, str):
            continue
        text = item.strip()
        lowered = text.lower()
        if not text or text.startswith("{"):
            continue
        if any(phrase in lowered for phrase in ("identity", "same person", "who the person", "guilt", "intent", "purpose", "role")):
            continue
        kept.append(text)
    return kept[:5]


def _evidence_brief(evidence: list[dict[str, Any]]) -> str:
    lines = []
    for item in evidence:
        lines.append(
            "\n".join(
                [
                    f"id: {item['id']}",
                    f"parent_id: {item.get('source_video_id')}",
                    f"camera: {item.get('camera_id')}",
                    f"location: {item.get('location')}",
                    f"start_seconds: {item.get('start_seconds')}",
                    f"end_seconds: {item.get('end_seconds')}",
                    f"labels: {', '.join(item.get('object_labels') or [])}",
                    f"score: {item.get('retrieval_score')}",
                    f"caption: {(item.get('observation') or '')[:500]}",
                ]
            )
        )
    return "\n---\n".join(lines)


def _merge_reasoner(
    parsed: dict[str, Any] | None,
    evidence: list[dict[str, Any]],
    fallback_findings: dict[str, Any],
    fallback_hypotheses: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    if not parsed:
        return fallback_findings, fallback_hypotheses, "deterministic"
    known = {item["id"] for item in evidence}
    llm_hypotheses = validate_hypotheses(parsed.get("hypotheses"), evidence)
    cited_hypotheses = []
    for index, hypothesis in enumerate(llm_hypotheses, start=1):
        hypothesis["id"] = f"hyp_llm_{index}"
        if any(evidence_id in hypothesis["statement"] for evidence_id in hypothesis["supporting_evidence_ids"]):
            cited_hypotheses.append(hypothesis)
    findings = {
        "observed": bullets_citing(parsed.get("observed"), known) or fallback_findings["observed"],
        "inferred": bullets_citing(parsed.get("inferred"), known) or fallback_findings["inferred"],
        "uncertain": bullets_citing(parsed.get("uncertain"), known) or fallback_findings["uncertain"],
        "next_steps": _plain_steps(parsed.get("next_steps")) or fallback_findings["next_steps"],
        "synthesis_note": fallback_findings.get("synthesis_note"),
    }
    hypotheses = list(fallback_hypotheses)
    seen = {item["statement"] for item in hypotheses}
    for hypothesis in cited_hypotheses:
        if hypothesis["statement"] not in seen:
            hypotheses.append(hypothesis)
    used_model = bool(cited_hypotheses) or any(
        bullets_citing(parsed.get(key), known) for key in ("observed", "inferred", "uncertain")
    )
    return findings, hypotheses, "wandb+validated" if used_model else "deterministic"


async def _expand_top_parents(provider: Any, hits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Pull every segment of the best parent recordings so a timeline can show order."""
    chosen_parents: list[str] = []
    for hit in hits:
        parent = hit.get("source_video_id")
        if parent and parent not in chosen_parents:
            chosen_parents.append(parent)
        if len(chosen_parents) >= MAX_PARENTS:
            break
    by_segment: dict[str, dict[str, Any]] = {}
    for hit in hits:
        if hit.get("source_video_id") in chosen_parents and hit.get("source_segment_id"):
            item = dict(hit)
            item["metadata"] = dict(item.get("metadata") or {})
            item["metadata"]["retrieval_role"] = "search_hit"
            by_segment[hit["source_segment_id"]] = item
    list_segments = getattr(provider, "list_segments", None)
    if list_segments is None:
        return list(by_segment.values())[:MAX_CLIPS], len(chosen_parents)
    for parent in chosen_parents:
        try:
            rows = await list_segments(parent)
        except ProviderError:
            continue
        for row in rows:
            key = row.get("source_segment_id")
            if not key or key in by_segment:
                continue
            item = dict(row)
            item["metadata"] = dict(item.get("metadata") or {})
            item["metadata"]["retrieval_role"] = "sibling_segment"
            item["retrieval_score"] = None
            by_segment[key] = item
    ordered = list(by_segment.values())
    ordered.sort(
        key=lambda item: (
            chosen_parents.index(item.get("source_video_id")) if item.get("source_video_id") in chosen_parents else 99,
            item.get("start_seconds") is None,
            item.get("start_seconds") or 0,
        )
    )
    return ordered[:MAX_CLIPS], len(chosen_parents)


async def _search_many(provider: Any, planned: list[tuple[str, str | None]], location: str | None) -> tuple[list, list[str], str | None, str | None, int]:
    hits: list[dict[str, Any]] = []
    errors: list[str] = []
    synthesis = None
    model = None
    calls = 0
    for query, camera in planned:
        filters: dict[str, str] = {}
        if camera:
            filters["camera_id"] = camera
        if location:
            filters["location"] = location
        try:
            result = await provider.search(query, filters, top_k=8, min_similarity=0.2)
            calls += 1
        except ProviderError as exc:
            errors.append(exc.message)
            continue
        hits.extend(result.get("hits") or [])
        if synthesis is None and result.get("synthesis"):
            synthesis = result["synthesis"]
            model = result.get("model")
    return hits, errors, synthesis, model, calls


async def run_investigation(
    *,
    provider: Any,
    reasoner: Any,
    case_id: str,
    question: str,
    cameras: list[str],
    location: str | None,
    new_id,
) -> dict[str, Any]:
    started = time.perf_counter()
    queries = plan_queries(question)
    planned = _search_plan(queries, cameras)
    stages = [
        {
            "id": "understand",
            "label": "Understand the request",
            "detail": "Using the investigator's wording. No entities were added beyond that text and the selected filters.",
        },
        {
            "id": "plan",
            "label": "Plan retrieval",
            "detail": "Queries: " + " | ".join(f"{query} [{camera or 'all selected cameras'}]" for query, camera in planned),
        },
    ]
    hits, errors, synthesis, synthesis_model, calls = await _search_many(provider, planned, location)
    if not hits and errors:
        raise ProviderError(errors[0], status_code=502)
    unique = _dedupe(hits)
    focused, expanded = await _expand_top_parents(provider, unique)
    evidence = []
    for hit in focused:
        item = dict(hit)
        item["id"] = new_id("ev")
        item["case_id"] = case_id
        evidence.append(item)
    stages.append(
        {
            "id": "retrieve",
            "label": "Retrieve evidence",
            "detail": (
                f"{len(evidence)} segments from {calls} searches"
                f" across {expanded} parent recording(s)."
                + (f" {len(errors)} searches failed." if errors else "")
            ),
        }
    )
    contradiction = contradiction_query(question)
    if calls < MAX_SEARCHES and evidence:
        camera = cameras[0] if cameras else None
        try:
            extra = await provider.search(
                contradiction,
                {"camera_id": camera} if camera else ({"location": location} if location else {}),
                top_k=4,
                min_similarity=0.2,
            )
            calls += 1
            known_segments = {item.get("source_segment_id") for item in evidence}
            added = 0
            for hit in extra.get("hits") or []:
                if hit.get("source_segment_id") in known_segments:
                    continue
                if len(evidence) >= MAX_CLIPS or added >= 2:
                    break
                item = dict(hit)
                item["id"] = new_id("ev")
                item["case_id"] = case_id
                item["metadata"] = dict(item.get("metadata") or {})
                item["metadata"]["retrieval_role"] = "contradiction_check"
                evidence.append(item)
                known_segments.add(item.get("source_segment_id"))
                added += 1
            stages.append(
                {
                    "id": "contradict",
                    "label": "Check contradictions",
                    "detail": f"Extra query “{contradiction}” added {added} segments.",
                }
            )
        except ProviderError as exc:
            stages.append(
                {
                    "id": "contradict",
                    "label": "Check contradictions",
                    "detail": f"Contradiction search failed: {exc.message}",
                }
            )
    timeline = build_timeline(case_id, evidence)
    stages.append(
        {
            "id": "timeline",
            "label": "Construct timeline",
            "detail": f"{len(timeline['groups'])} parent recording group(s). Groups are not on one clock.",
        }
    )
    hypotheses = deterministic_hypotheses(case_id, evidence)
    findings = deterministic_findings(evidence, timeline)
    if synthesis:
        findings["synthesis_note"] = (
            f"Video-service synthesis ({synthesis_model or 'Cosmos via VSS'}): {synthesis[:1200]}"
        )
    reasoner_name = "deterministic"
    if evidence and reasoner is not None and getattr(reasoner, "name", "") != "deterministic":
        prompt = (
            f"Question: {question}\n\nEvidence:\n{_evidence_brief(evidence)}\n\n"
            "Return JSON with keys observed, inferred, uncertain, next_steps, hypotheses. "
            "hypotheses items need statement, supporting_evidence_ids, contradicting_evidence_ids, "
            "unresolved_questions, status."
        )
        text, _model = await reasoner.complete(SYSTEM, prompt)
        parsed = parse_json_object(text or "")
        findings, hypotheses, reasoner_name = _merge_reasoner(parsed, evidence, findings, hypotheses)
    for hypothesis in hypotheses:
        hypothesis["case_id"] = case_id
    stages.append(
        {
            "id": "hypotheses",
            "label": "Form hypotheses",
            "detail": f"{len(hypotheses)} hypotheses retained after citation checks. Reasoner: {reasoner_name}.",
        }
    )
    stages.append(
        {
            "id": "findings",
            "label": "Produce findings",
            "detail": f"{len(findings['observed'])} cited observations. Unsupported citations were dropped.",
        }
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return {
        "case_id": case_id,
        "question": question,
        "stages": stages,
        "evidence": evidence,
        "timeline": timeline,
        "hypotheses": hypotheses,
        "findings": findings,
        "reasoner": reasoner_name,
        "retrieval_calls": calls,
        "elapsed_ms": elapsed_ms,
    }


def extractive_answer(question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    words = {word for word in question.lower().split() if len(word) > 3}
    ranked = []
    for item in evidence:
        text = (item.get("observation") or "").lower()
        score = sum(1 for word in words if word in text)
        ranked.append((score, item.get("retrieval_score") or 0, item))
    ranked.sort(key=lambda row: (row[0], row[1]), reverse=True)
    chosen = [item for score, _rank, item in ranked[:3] if score > 0] or [item for _s, _r, item in ranked[:2]]
    if not chosen:
        return {
            "content": "This case has no retrieved evidence yet. Run an investigation before asking follow-up questions.",
            "evidence_ids": [],
            "reasoner": "deterministic",
        }
    lines = [
        "These indexed captions are the closest items already retrieved for this case. They are model descriptions, not a conclusion."
    ]
    ids = []
    for item in chosen:
        ids.append(item["id"])
        lines.append(
            f"{item['id']} ({item.get('camera_id')} {item.get('start_seconds')}–{item.get('end_seconds')}s): {item.get('observation')}"
        )
    lines.append("What remains uncertain: captions can be wrong, and clips from different parent recordings are not on one clock.")
    return {"content": "\n\n".join(lines), "evidence_ids": ids, "reasoner": "deterministic"}


async def answer_question(reasoner: Any, question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    fallback = extractive_answer(question, evidence)
    if not evidence or reasoner is None or getattr(reasoner, "name", "") == "deterministic":
        return fallback
    prompt = (
        f"Question: {question}\n\nEvidence:\n{_evidence_brief(evidence)}\n\n"
        'Return JSON {"answer": "...", "evidence_ids": ["..."]}. '
        "The answer must include every evidence id it relies on."
    )
    text, _model = await reasoner.complete(SYSTEM, prompt)
    parsed = parse_json_object(text or "")
    if not parsed:
        return fallback
    known = {item["id"] for item in evidence}
    ids = [item for item in parsed.get("evidence_ids") or [] if item in known]
    answer = str(parsed.get("answer") or "").strip()
    if not ids or not answer or not any(item in answer for item in ids):
        return fallback
    return {"content": answer, "evidence_ids": ids, "reasoner": "wandb+validated"}
