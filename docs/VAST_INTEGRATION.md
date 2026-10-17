# VAST integration

Sherlocked calls the team's already-deployed Video Search & Summary API. It does not redeploy the ingest pipeline, Cosmos, YOLO, or Embed endpoints.

Verified on host `bc-pool-280` as `team-17` (Kubernetes context `team-17`).

## Environment

These names are set in the VM environment: `USERNAME`, `INGRESS_URL`, `PIPELINE`, `S3_ENDPOINT`, `S3_CHUNKS_BUCKET`, `S3_SEGMENTS_BUCKET`, `VASTDB_BUCKET`, `VDB_SCHEMA`, `VDB_COLLECTION`, `VDB_PROMPTS_COLLECTION`, `WANDB_TEAM`, `WANDB_PROJECT`, `WANDB_API_KEY`, `ACCESS_KEY`, `SECRET_KEY`, `PASSWORD`, `GPU_BEARER_TOKEN`.

`VDB_ENDPOINT`, `COSMOS3_REASON_URL`, `COSMOS_EMBED1_URL`, and `YOLO_URL` are not set in this VM's environment or in `/config/team-17.config`. Sherlocked does not call those GPU hosts directly. Cosmos Reason captions, Cosmos Embed search, and YOLO object labels are already stored on each indexed segment and are read through the retrieval API.

## Skills used

| Skill | What Sherlocked uses it for |
| --- | --- |
| `retrieval/login` | `POST /api/v1/auth/login`, then `GET /api/v1/auth/me`. The JWT stays on the server. |
| `retrieval/dashboard` | `GET /api/v1/dashboard/stats` for catalogue counts, cameras, locations, and pipeline health. |
| `retrieval/list-metadata` | Filter fields are `camera_id`, `capture_type`, `location`, and `object_classes`. |
| `retrieval/search` | `POST /api/v1/search`. Hits include `source`, `original_video`, `segment_start_sec`, `segment_end_sec`, `reasoning_content`, `similarity_score`, `object_classes`, and `llm_synthesis`. |
| `retrieval/videos` | `GET /api/v1/videos/explore` for the catalogue. `GET /api/v1/videos/stream?source=&token=` is proxied by Sherlocked so the browser never sees the token. |
| `retrieval/agent-qa` | `GET /api/v1/tools/segments?original_video=` loads the other segments of a matched parent recording. The agent ask route exists; Sherlocked does its own citation-checked reasoning on top of search instead of treating that answer as the investigation. |
| `deployment/deploy-app-no-registry` | Kubernetes Deployment in the team namespace, public `python:3.12-slim` image, code in a ConfigMap, Ingress path `/app`. |

Re-ingest skills were read and not run. The warehouse captions already describe people and forklifts.

## Live checks

- Login and `/auth/me` succeeded for `team-17`.
- Dashboard: 3,537 indexed clips, 612 videos, pipeline alignment `healthy: true`, reasoning and perception coverage 100%.
- Cameras include `sdg_warehouse_cam-2` (60 segments, location `warehouse3`), plus street, traffic, neighbourhood, and indoor cameras.
- Search `person near a forklift` on `sdg_warehouse_cam-2` returned real segment URIs, captions, offsets, and scores around 0.55–0.59.
- Segment playback through Sherlocked returned `video/mp4` bytes beginning with `ftypisom`.
- YOLO labels arrive as `object_classes` on the segment row (for example `person`). `max_detection_conf` is a detector box score, not a probability that an incident occurred.
- Weights & Biases serverless inference answered a JSON probe with `meta-llama/Llama-3.1-8B-Instruct` at `https://api.inference.wandb.ai/v1`. If that call fails or cites an id that was not retrieved, Sherlocked keeps the deterministic findings.

## Playback

`GET /api/media/stream?item_id=&which=segment|parent` only streams ids Sherlocked has stored from search or an investigation. The server attaches the VSS JWT. `which=parent` is used when the parent file is long enough to seek to `segment_start_sec`. Short parents fall back to the segment file, which already starts at the matched moment.

The deployed pod cannot resolve the public ingress hostname. It calls the in-cluster Service `video-backend-service` on port 8000. The browser still opens the workshop App button, which routes to Ingress path `/app`.

## Errors

- 401: the provider drops its token and logs in once more.
- Search or login failure: the API returns the provider error status and does not invent an empty success investigation.
- Missing playback id: 404.
- Mock provider: every observation is prefixed `SYNTHETIC FIXTURE`, and playback returns 404.
