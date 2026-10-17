# API contract

Base path `/api`. Errors use `{"detail": "..."}`. A provider failure is not returned as HTTP 200.

| Method | Path | Body | Response |
| --- | --- | --- | --- |
| GET | `/health` | | Process probe `{status: ok}`. Does not call VAST. |
| GET | `/api/health` | | `{status, provider, synthetic, reasoner, video}`. `status` is `degraded` when login fails. |
| GET | `/api/videos` | | Catalogue: cameras, locations, capture types, overview counts, sample videos. |
| POST | `/api/videos/search` | `{query, camera_id?, location?, capture_type?, top_k?}` | `{results: Evidence[], synthesis, synthesis_model, synthetic, score_meaning}` |
| GET | `/api/cases` | | `{cases: Case[]}` |
| POST | `/api/cases` | `{title, description, location?, incident_start?, incident_end?, camera_ids?}` | `Case` (201) |
| GET | `/api/cases/{id}` | | `Case` or 404 |
| POST | `/api/cases/{id}/investigate` | `{question?}` | `Investigation` |
| GET | `/api/cases/{id}/evidence` | | `{evidence: Evidence[]}` |
| GET | `/api/cases/{id}/timeline` | | `{groups, note}` |
| GET | `/api/cases/{id}/hypotheses` | | `{hypotheses}` |
| GET | `/api/cases/{id}/messages` | | `{messages}` |
| POST | `/api/cases/{id}/ask` | `{question}` | `{answer, evidence_ids, reasoner, messages}` |
| GET | `/api/cases/{id}/report` | | `{case, investigation}` |
| GET | `/api/cases/{id}/report.html` | | HTML report |
| GET | `/api/media/stream?item_id&which=segment\|parent` | | Video bytes, or 404 |

`Evidence` fields: `id`, `case_id`, `source_video_id`, `source_segment_id`, `camera_id`, `location`, `start_seconds`, `end_seconds`, `observation`, `object_labels`, `source_description`, `retrieval_score`, `evidence_type`, `filename`, `metadata`.

`Hypothesis.status` is `supported`, `unverified`, `contradicted`, or `insufficient`.

Timeline events set `absolute_time` to null. `verification_status` for retrieved captions is `observed`.
