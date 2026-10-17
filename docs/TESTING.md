# Testing

Commands were run on the workshop VM on 17 October 2026.

## Backend

```bash
cd sherlocked/backend && ../.venv/bin/python -m pytest -q
```

Result: **14 passed**.

Covered:

- `/health` and `/api/health` with the mock provider flagged synthetic
- Case create, fetch, list
- Empty title rejected (422)
- Unknown case rejected (404)
- Mock search observations contain `SYNTHETIC FIXTURE`
- Investigation citations are a subset of retrieved ids
- Timeline offsets increase inside a parent
- Two parent recordings stay in two groups and have no absolute time
- Empty camera filter returns no hits
- Follow-up answers only cite retrieved ids
- VAST hit normalisation keeps source URI and segment offsets
- Unknown hypothesis ids are removed, and a single-parent citation cannot stay `supported`

## Frontend

```bash
cd sherlocked/frontend && npm run build
```

Result: `tsc -b` and Vite build succeeded. The production bundle is about 316 KB of JavaScript and 14 KB of CSS before gzip.

## Live archive

Against the running API with `VIDEO_PROVIDER=vast`:

- `GET /api/health`: `status=ok`, `provider=vast`, `synthetic=false`, authenticated as `team-17`
- `GET /api/videos`: 3,537 indexed clips, 13 cameras
- `POST /api/videos/search` for a person near a forklift on `sdg_warehouse_cam-2`: 4 hits, not synthetic
- `GET /api/media/stream`: HTTP 200, `content-type: video/mp4`, body starts with an ISO BMFF `ftyp` box
- `POST /api/cases/{id}/investigate`: completed in about 18 seconds, 4 retrieval calls, reasoner `wandb+validated`, sibling segments attached to the top parent recordings (0–5s and 5–10s on `ceiling_04`, `eye_00`, and `ceiling_03`)

No latency series beyond that single investigation was recorded. Do not quote a percentage of unsupported claims beyond the unit test that strips unknown ids.

## Deployed app

`scripts/deploy.sh` applied Deployment, Service, and Ingress `sherlocked` in namespace `team-17`. The pod calls the in-cluster `video-backend-service` because the public ingress hostname does not resolve inside the cluster.

After rollout:

- `GET /app/` returned 200 and the Sherlocked HTML
- `GET /app/health` returned `{"status":"ok"}`
- `GET /app/api/health` returned `status=ok`, `provider=vast`, `synthetic=false`, authenticated
- `POST /app/api/videos/search` returned a real `sdg_warehouse_cam-2` segment
- `GET /app/api/media/stream` returned `video/mp4` beginning with `ftyp`
- The frontend JavaScript bundle returned 200

The first health check during rollout returned 503 until the new pod finished installing dependencies. A later check passed.
