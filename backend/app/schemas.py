"""API models. Retrieval scores are similarity ranks, not probabilities."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    location: str | None = None
    incident_start: str | None = None
    incident_end: str | None = None
    camera_ids: list[str] = Field(default_factory=list)


class CaseOut(BaseModel):
    id: str
    title: str
    description: str
    location: str | None = None
    incident_start: str | None = None
    incident_end: str | None = None
    status: str
    camera_ids: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    evidence_count: int = 0


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    camera_id: str | None = None
    location: str | None = None
    capture_type: str | None = None
    top_k: int = Field(default=8, ge=1, le=20)


class InvestigateIn(BaseModel):
    question: str | None = Field(default=None, max_length=4000)


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class SafetyActionIn(BaseModel):
    camera: str = Field(min_length=4, max_length=16)
    kind: str = Field(pattern="^(risk|training|prevent|escalate)$")
    body: str = Field(default="", max_length=20000)
    payload: dict[str, Any] = Field(default_factory=dict)


class SafetyActionUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=20000)
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceOut(BaseModel):
    id: str
    case_id: str | None = None
    source_video_id: str | None = None
    source_segment_id: str | None = None
    camera_id: str | None = None
    location: str | None = None
    start_seconds: float | None = None
    end_seconds: float | None = None
    observation: str
    object_labels: list[str] = Field(default_factory=list)
    source_description: str = ""
    retrieval_score: float | None = None
    evidence_type: str = "model_caption"
    filename: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineEventOut(BaseModel):
    id: str
    case_id: str | None = None
    description: str
    event_type: str
    absolute_time: str | None = None
    relative_time: float | None = None
    end_seconds: float | None = None
    evidence_ids: list[str]
    verification_status: str


class TimelineGroupOut(BaseModel):
    group_id: str
    camera_id: str | None = None
    location: str | None = None
    label: str
    clock: str = "relative_to_parent"
    clock_note: str
    events: list[TimelineEventOut]


class TimelineOut(BaseModel):
    groups: list[TimelineGroupOut]
    note: str


class HypothesisOut(BaseModel):
    id: str
    case_id: str | None = None
    statement: str
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    status: str


class FindingsOut(BaseModel):
    observed: list[str]
    inferred: list[str]
    uncertain: list[str]
    next_steps: list[str]
    synthesis_note: str | None = None


class StageOut(BaseModel):
    id: str
    label: str
    detail: str


class MessageOut(BaseModel):
    id: str
    case_id: str
    role: str
    content: str
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: str


class InvestigationOut(BaseModel):
    case_id: str
    question: str
    stages: list[StageOut]
    evidence: list[EvidenceOut]
    timeline: TimelineOut
    hypotheses: list[HypothesisOut]
    findings: FindingsOut
    messages: list[MessageOut]
    reasoner: str
    retrieval_calls: int
    elapsed_ms: int


class VideoSourceOut(BaseModel):
    id: str
    provider: str
    camera_id: str | None = None
    location: str | None = None
    title: str
    duration_seconds: float | None = None
    capture_start_time: str | None = None
    playback_url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
