"""Sherlocked HTTP API."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from app.providers.base import ProviderError
from app.report import render_report
from app.schemas import AskIn, CaseCreate, InvestigateIn, SafetyActionIn, SafetyActionUpdate, SearchIn
from app.services.safety import (
    camera_by_code,
    default_controls,
    detections_for,
    draft_assessment,
    investigation,
    load_wall,
    parent_source,
    render_safety_html,
    training_task,
)
from app.services.investigation import answer_question, run_investigation
from app.store import Store, new_id

router = APIRouter()


def store_of(request: Request) -> Store:
    return request.app.state.store


def provider_of(request: Request):
    return request.app.state.provider


def reasoner_of(request: Request):
    return request.app.state.reasoner


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    provider = provider_of(request)
    payload: dict[str, Any] = {
        "status": "ok",
        "service": "sherlocked",
        "provider": provider.name,
        "synthetic": provider.synthetic,
        "reasoner": reasoner_of(request).name,
    }
    try:
        payload["video"] = await provider.health()
    except ProviderError as exc:
        payload["status"] = "degraded"
        payload["video"] = {"authenticated": False, "detail": exc.message}
    return payload


@router.get("/videos")
async def videos(request: Request) -> dict[str, Any]:
    catalog = await provider_of(request).list_catalog()
    return catalog


@router.post("/videos/search")
async def search_videos(body: SearchIn, request: Request) -> dict[str, Any]:
    filters = {}
    if body.camera_id:
        filters["camera_id"] = body.camera_id
    if body.location:
        filters["location"] = body.location
    if body.capture_type:
        filters["capture_type"] = body.capture_type
    result = await provider_of(request).search(body.query, filters, top_k=body.top_k)
    hits = store_of(request).save_hits(result.get("hits") or [])
    return {
        "query": body.query,
        "provider": provider_of(request).name,
        "synthetic": provider_of(request).synthetic,
        "results": hits,
        "synthesis": result.get("synthesis"),
        "synthesis_model": result.get("model"),
        "score_meaning": "hybrid_similarity" if not provider_of(request).synthetic else "fixture_rank",
    }


@router.get("/cases")
def list_cases(request: Request) -> dict[str, Any]:
    return {"cases": store_of(request).list_cases()}


@router.post("/cases", status_code=201)
def create_case(body: CaseCreate, request: Request) -> dict[str, Any]:
    return store_of(request).create_case(body.model_dump())


@router.get("/cases/{case_id}")
def get_case(case_id: str, request: Request):
    case = store_of(request).get_case(case_id)
    if not case:
        return JSONResponse({"detail": "Case not found"}, status_code=404)
    return case


def _investigation_or_empty(store: Store, case_id: str) -> dict[str, Any]:
    payload = store.get_investigation(case_id) or {}
    return payload


@router.get("/cases/{case_id}/evidence")
def case_evidence(case_id: str, request: Request):
    store = store_of(request)
    if not store.get_case(case_id):
        return JSONResponse({"detail": "Case not found"}, status_code=404)
    payload = _investigation_or_empty(store, case_id)
    return {"evidence": payload.get("evidence") or []}


@router.get("/cases/{case_id}/timeline")
def case_timeline(case_id: str, request: Request):
    store = store_of(request)
    if not store.get_case(case_id):
        return JSONResponse({"detail": "Case not found"}, status_code=404)
    payload = _investigation_or_empty(store, case_id)
    return payload.get("timeline") or {
        "groups": [],
        "note": "No investigation has been run.",
    }


@router.get("/cases/{case_id}/hypotheses")
def case_hypotheses(case_id: str, request: Request):
    store = store_of(request)
    if not store.get_case(case_id):
        return JSONResponse({"detail": "Case not found"}, status_code=404)
    payload = _investigation_or_empty(store, case_id)
    return {"hypotheses": payload.get("hypotheses") or []}


@router.get("/cases/{case_id}/messages")
def case_messages(case_id: str, request: Request):
    store = store_of(request)
    if not store.get_case(case_id):
        return JSONResponse({"detail": "Case not found"}, status_code=404)
    return {"messages": store.list_messages(case_id)}


@router.post("/cases/{case_id}/investigate")
async def investigate(case_id: str, body: InvestigateIn, request: Request):
    store = store_of(request)
    case = store.get_case(case_id)
    if not case:
        return JSONResponse({"detail": "Case not found"}, status_code=404)
    question = (body.question or case["description"]).strip()
    store.set_status(case_id, "investigating")
    store.clear_messages(case_id)
    store.add_message(case_id, "user", question, [])
    result = await run_investigation(
        provider=provider_of(request),
        reasoner=reasoner_of(request),
        case_id=case_id,
        question=question,
        cameras=case.get("camera_ids") or [],
        location=case.get("location"),
        new_id=new_id,
    )
    summary = _summary(result)
    message = store.add_message(
        case_id,
        "assistant",
        summary,
        [item["id"] for item in result["evidence"]],
    )
    result["messages"] = store.list_messages(case_id)
    store.save_investigation(case_id, result)
    result["messages"] = store.list_messages(case_id)
    # The message created above is already listed; keep the variable used.
    _ = message
    return result


def _summary(result: dict[str, Any]) -> str:
    observed = result["findings"].get("observed") or []
    head = observed[:3]
    text = "Investigation finished. Observations are indexed captions, not verified findings.\n\n"
    text += "\n\n".join(head) if head else "No matching segments were retrieved."
    if len(observed) > 3:
        text += f"\n\n{len(observed) - 3} more observations are in the evidence list."
    return text


@router.post("/cases/{case_id}/ask")
async def ask(case_id: str, body: AskIn, request: Request):
    store = store_of(request)
    if not store.get_case(case_id):
        return JSONResponse({"detail": "Case not found"}, status_code=404)
    payload = store.get_investigation(case_id) or {}
    evidence = payload.get("evidence") or []
    store.add_message(case_id, "user", body.question, [])
    answer = await answer_question(reasoner_of(request), body.question, evidence)
    store.add_message(case_id, "assistant", answer["content"], answer["evidence_ids"])
    return {
        "answer": answer["content"],
        "evidence_ids": answer["evidence_ids"],
        "reasoner": answer["reasoner"],
        "messages": store.list_messages(case_id),
    }


@router.get("/cases/{case_id}/report")
def report(case_id: str, request: Request):
    store = store_of(request)
    case = store.get_case(case_id)
    if not case:
        return JSONResponse({"detail": "Case not found"}, status_code=404)
    investigation = store.get_investigation(case_id)
    return {"case": case, "investigation": investigation}


@router.get("/cases/{case_id}/report.html")
def report_html(case_id: str, request: Request):
    store = store_of(request)
    case = store.get_case(case_id)
    if not case:
        return JSONResponse({"detail": "Case not found"}, status_code=404)
    return HTMLResponse(render_report(case, store.get_investigation(case_id)))


@router.get("/safety/wall")
def safety_wall(request: Request) -> dict[str, Any]:
    wall = load_wall()
    actions = store_of(request).list_safety_actions()
    reviewed = {item["camera_code"] for item in actions}
    wall["awaiting_review"] = len([code for code in wall["flagged_cameras"] if code not in reviewed])
    wall["actions"] = actions
    return wall


@router.get("/safety/cameras/{code}")
def safety_camera(code: str):
    view = investigation(code)
    if not view:
        return JSONResponse({"detail": "Camera not on the replay wall."}, status_code=404)
    view["controls"] = default_controls(view["category"])
    return view


@router.get("/safety/cameras/{code}/detections")
async def safety_detections(code: str, request: Request):
    if not camera_by_code(code):
        return JSONResponse({"detail": "Camera not on the replay wall."}, status_code=404)
    return await detections_for(provider_of(request), code)


@router.get("/safety/actions")
def safety_actions(request: Request) -> dict[str, Any]:
    return {"actions": store_of(request).list_safety_actions()}


@router.post("/safety/actions", status_code=201)
async def create_safety_action(body: SafetyActionIn, request: Request):
    view = investigation(body.camera)
    if not view:
        return JSONResponse({"detail": "Camera not on the replay wall."}, status_code=404)
    store = store_of(request)
    if body.kind == "risk":
        drafted = await draft_assessment(reasoner_of(request), view)
        text = body.body.strip() or drafted["body"]
        action = store.add_safety_action(
            body.camera,
            "risk",
            f"Risk note {body.camera}",
            text,
            "draft",
            {"reasoner": drafted["reasoner"], "model": drafted["model"], **body.payload},
        )
        return action
    if body.kind == "training":
        task = training_task(view)
        return store.add_safety_action(body.camera, "training", task["title"], task["body"], "queued_demo", body.payload)
    if body.kind == "prevent":
        return store.add_safety_action(
            body.camera,
            "prevent",
            "Proposed separation overlay",
            body.body.strip() or "Proposed pedestrian boundary added to the corrective-action plan. Not a physical simulation.",
            "proposed",
            body.payload,
        )
    return store.add_safety_action(
        body.camera,
        "escalate",
        f"Flagged for safety officer · {body.camera}",
        body.body.strip() or "Pending human review. No external message was sent.",
        "pending_human_review",
        body.payload,
    )


@router.patch("/safety/actions/{action_id}")
def update_safety_action(action_id: str, body: SafetyActionUpdate, request: Request):
    updated = store_of(request).update_safety_action(action_id, body.body, body.payload)
    if not updated:
        return JSONResponse({"detail": "Action not found."}, status_code=404)
    return updated


@router.get("/safety/cameras/{code}/report.html")
def safety_report(code: str, request: Request):
    view = investigation(code)
    if not view:
        return JSONResponse({"detail": "Camera not on the replay wall."}, status_code=404)
    actions = [item for item in store_of(request).list_safety_actions(code)]
    return HTMLResponse(render_safety_html(view, actions))


@router.get("/safety/stream")
async def safety_stream(camera: str, request: Request):
    source = parent_source(camera)
    if not source:
        return JSONResponse({"detail": "Camera not on the replay wall."}, status_code=404)
    upstream = await provider_of(request).media_url(source)
    client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    headers = {}
    if request.headers.get("range"):
        headers["Range"] = request.headers["range"]
    try:
        upstream_response = await client.send(client.build_request("GET", upstream, headers=headers), stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise ProviderError(f"Playback upstream failed: {exc.__class__.__name__}") from exc

    async def body_iter():
        try:
            async for chunk in upstream_response.aiter_bytes(64 * 1024):
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    passthrough = {}
    for header in ("content-type", "content-length", "content-range", "accept-ranges"):
        if header in upstream_response.headers:
            passthrough[header] = upstream_response.headers[header]
    content_type = passthrough.get("content-type", "")
    if source.endswith(".mp4") and (not content_type or "octet-stream" in content_type):
        passthrough["content-type"] = "video/mp4"
    return StreamingResponse(body_iter(), status_code=upstream_response.status_code, headers=passthrough)


@router.get("/media/stream")
async def stream_media(item_id: str, request: Request, which: str = "segment"):
    playback = store_of(request).get_playback(item_id)
    if not playback:
        return JSONResponse({"detail": "No playable item with that id."}, status_code=404)
    source = playback["parent_source"] if which == "parent" and playback.get("parent_source") else playback.get("segment_source")
    if not source:
        return JSONResponse({"detail": "This item has no source URI."}, status_code=404)
    upstream = await provider_of(request).media_url(source)
    client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    headers = {}
    if request.headers.get("range"):
        headers["Range"] = request.headers["range"]
    try:
        upstream_response = await client.send(client.build_request("GET", upstream, headers=headers), stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise ProviderError(f"Playback upstream failed: {exc.__class__.__name__}") from exc

    async def body():
        try:
            async for chunk in upstream_response.aiter_bytes(64 * 1024):
                yield chunk
        finally:
            await upstream_response.aclose()
            await client.aclose()

    passthrough = {}
    for header in ("content-type", "content-length", "content-range", "accept-ranges"):
        if header in upstream_response.headers:
            passthrough[header] = upstream_response.headers[header]
    content_type = passthrough.get("content-type", "")
    if source.endswith(".mp4") and (not content_type or "octet-stream" in content_type):
        passthrough["content-type"] = "video/mp4"
    return StreamingResponse(body(), status_code=upstream_response.status_code, headers=passthrough)
