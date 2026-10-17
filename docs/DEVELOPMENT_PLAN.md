# Development plan

| Phase | State |
| --- | --- |
| 0. VM, skills, login, dashboard, search, playback | Done. Team-17 archive is healthy. |
| 1. FastAPI, SQLite cases, mock provider, React app | Done. 12 pytest tests pass. Frontend build succeeds. |
| 2. Vast provider, search, proxied playback | Done. A warehouse segment streamed as `video/mp4`. |
| 3. Investigation with parent expansion, hypotheses, follow-up ask | Done against live search. |
| 4. Workspace UI | Done and served by the API from `frontend/dist`. |
| 5. Kubernetes `/app` deploy | Done. Pod `sherlocked` is Running. `GET /app/api/health` authenticates to VAST. Search and segment playback succeed through the Ingress. Open the workshop App button. |
| 6. Re-ingest, cross-camera identity, uploads | Not in scope. Captions are already usable. Upload of new footage is not part of this build. |

Cases live in SQLite on the pod and reset when the pod restarts. The video archive does not.
