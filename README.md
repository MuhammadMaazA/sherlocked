# Sherlocked

Every clue. Every frame. Every answer backed by evidence.

Sherlocked is an investigation workspace on top of the VAST Builders Challenge video archive. An investigator describes an incident. The app searches indexed footage, lines up segments inside each parent recording, and returns findings that cite those segments. It does not decide guilt, infer intent, or identify a person.

## What it does

- Creates an investigation case and stores it in SQLite.
- Searches the live VAST index (hybrid caption and embedding search).
- Plays the matched segment through a backend proxy so the browser never receives the VSS token.
- Builds a timeline per parent recording. Offsets are seconds inside that recording. Different recordings are not placed on one clock.
- Forms hypotheses only from retrieved captions. A `supported` status requires two segments from the same parent. Unknown evidence ids are dropped.
- Asks follow-up questions against the evidence already retrieved.
- Renders an HTML report.

The demo case is warehouse camera `sdg_warehouse_cam-2`: indexed captions describe a person near a forklift, including a segment where the forklift begins to move and the person moves away. Those captions come from separate parent files, including `ceiling_04` and `eye_00` renders. See `docs/DEMO_SCENARIO.md`.

## Stack

- React, TypeScript, Vite, Tailwind CSS, TanStack Query, React Router
- FastAPI, Pydantic, httpx, SQLite
- VAST retrieval API (Cosmos Reason captions, Cosmos Embed search, YOLO labels already on each segment)
- Weights & Biases serverless inference for citation-checked wording, with a deterministic fallback

## Architecture

The browser talks only to Sherlocked. Sherlocked talks to the team's Video Search & Summary API using `INGRESS_URL` or `VSS_URL`. Details are in `docs/ARCHITECTURE.md` and `docs/VAST_INTEGRATION.md`.

## Local development

From `sherlocked/`, with the workshop environment already exported:

```bash
make test
make build
make api
```

Open `http://127.0.0.1:8000`.

`make web` runs the Vite dev server on port 5173 and proxies `/api` to port 8000.

`VIDEO_PROVIDER=mock` and `REASONING_PROVIDER=none` run without the archive. Mock observations are labelled `SYNTHETIC FIXTURE` and have no video.

Environment names are listed in `.env.example`. Do not commit values.

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest -q
```

Results and the live checks that were actually run are in `docs/TESTING.md`.

## Deployment

`scripts/deploy.sh` builds the frontend with base `/app/`, packs the app under the ConfigMap size limit, and applies a Deployment, Service, and Ingress at path `/app` in the team namespace. It follows the organiser skill `deployment/deploy-app-no-registry`.

After it succeeds, open [https://workshop.thecosmoslabs.com](https://workshop.thecosmoslabs.com) and click **App**.

## Demo

`docs/DEMO_SCRIPT.md` is the three-minute path. Use the warehouse preset on the dashboard.

## Limitations

- New video upload is not part of this app. The archive was already indexed.
- Captions are model text. Similarity scores are not probabilities.
- Clips that do not share a parent recording are not synchronised.
- Similar clothing or a similar forklift is not treated as the same person or vehicle.
- SQLite on the pod is wiped when the pod restarts. The VAST index is not.
- GPU host variables `COSMOS3_REASON_URL`, `COSMOS_EMBED1_URL`, and `YOLO_URL` are not set on this VM. Sherlocked uses the captions, embeddings, and labels the pipeline already wrote.

## Layout

Application code lives in this directory. The parent `vast-builders-challenge` tree is the organiser repository (skills, docs, and team config). This directory is its own Git repository.
