# Architecture

Sherlocked is a single FastAPI process and a React workspace. VAST remains the source of truth for video. SQLite stores cases, chat, and the latest investigation snapshot for this app only.

```text
Browser
  → Sherlocked API  /api/*
       → VastVideoProvider  (JWT, search, segments, stream proxy)
       → WandbReasoner      (optional structured text, citation-checked)
       → SQLite             (cases and snapshots)
  → Video element  /api/media/stream
```

## Evidence rules

- An observation is the indexed Cosmos Reason caption, copied with its segment URI, parent URI, camera, and offsets.
- A timeline group is one parent recording. `relative_time` is `segment_start_sec` inside that parent. `absolute_time` is left empty. Ingest timestamps are not treated as capture time.
- A hypothesis can be `supported` only when at least two cited segments share one parent. Otherwise it stays `unverified`. Opposing motion language inside one parent is marked `contradicted`, which means the captions disagree, not that either caption is proven false.
- Retrieval scores stay labelled as hybrid similarity.
- The language model is discarded when its JSON is invalid or when it cites an id that was not retrieved.

## Investigation budget

At most four planned searches, one contradiction search, three parent recordings expanded via `/tools/segments`, and twelve segments. One language-model call.

## Providers

`VIDEO_PROVIDER=vast` uses the workshop environment. `VIDEO_PROVIDER=mock` returns labelled synthetic fixtures and no media. `REASONING_PROVIDER=none` skips Weights & Biases.

## Deployment shape

The workshop path is one Python container serving the built frontend and the API, published at Ingress `/app` on the team host. See `scripts/deploy.sh` and `deployment/deploy-app-no-registry`.
