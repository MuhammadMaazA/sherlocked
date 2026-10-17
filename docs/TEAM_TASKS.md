# Team tasks

One coding agent implemented the tracks in dependency order inside `sherlocked/`. The organiser repository above this directory was not modified.

## Developer A — retrieval

- `backend/app/providers/vast.py`
- `docs/VAST_INTEGRATION.md`
- Live login, search, segment expansion, and the stream proxy

## Developer B — investigation

- `backend/app/services/`
- `backend/app/providers/reasoning.py`
- Citation checks, parent-relative timelines, contradiction query

## Developer C — interface

- `frontend/`
- Dashboard, case form, three-pane workspace, timeline, report

## Developer D — API and demo

- `backend/app/api/routes.py`
- `backend/app/store.py`
- `backend/tests/`
- `scripts/smoke_test.sh`, `scripts/deploy.sh`
- `docs/DEMO_SCRIPT.md`

Do not start a large re-ingest. The shared index is already healthy.
