"""Drop citations the retriever did not actually return."""

from __future__ import annotations

from typing import Any


STATUSES = {"supported", "unverified", "contradicted", "insufficient"}


def keep_known(ids: list[str] | None, known: set[str]) -> list[str]:
    kept: list[str] = []
    for item in ids or []:
        if item in known and item not in kept:
            kept.append(item)
    return kept


def validate_hypotheses(raw: list[dict[str, Any]] | None, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    known = {item["id"] for item in evidence}
    parents = {item["id"]: item.get("source_video_id") for item in evidence}
    cleaned: list[dict[str, Any]] = []
    for index, hypothesis in enumerate(raw or []):
        if not isinstance(hypothesis, dict):
            continue
        supporting = keep_known(hypothesis.get("supporting_evidence_ids"), known)
        contradicting = keep_known(hypothesis.get("contradicting_evidence_ids"), known)
        if not supporting:
            continue
        status = hypothesis.get("status") or "unverified"
        if status not in STATUSES:
            status = "unverified"
        parent_ids = {parents.get(item) for item in supporting}
        if status == "supported" and (len(supporting) < 2 or len(parent_ids) != 1):
            status = "unverified"
        if contradicting and status == "supported":
            status = "unverified"
        questions = [str(item) for item in (hypothesis.get("unresolved_questions") or []) if str(item).strip()]
        cleaned.append(
            {
                "id": hypothesis.get("id") or f"hyp_{index + 1}",
                "statement": str(hypothesis.get("statement") or "").strip(),
                "supporting_evidence_ids": supporting,
                "contradicting_evidence_ids": contradicting,
                "unresolved_questions": questions[:4],
                "status": status,
            }
        )
    return [item for item in cleaned if item["statement"]]


def bullets_citing(lines: list | None, known: set[str]) -> list[str]:
    kept: list[str] = []
    for line in lines or []:
        text = ""
        if isinstance(line, str):
            text = line.strip()
        elif isinstance(line, dict):
            evidence_id = str(line.get("id") or line.get("evidence_id") or "")
            description = line.get("observation") or line.get("description") or line.get("text") or line.get("statement")
            if evidence_id in known and description:
                text = f"{evidence_id}: {description}".strip()
        if text and any(evidence_id in text for evidence_id in known):
            kept.append(text)
    return kept
