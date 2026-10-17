# Agent notes

- This directory is the Sherlocked Git repository. The parent folder is the VAST workshop repo. Do not commit Sherlocked from the parent, and do not commit secrets.
- Call VAST through `backend/app/providers/vast.py`. Read `.cursor/skills/retrieval/` in the parent repo before changing endpoints.
- `VIDEO_PROVIDER=mock` is synthetic. Do not describe those fixtures as archive footage.
- Every finding shown to an investigator must cite an evidence id that search or `/tools/segments` returned.
- Do not order different parent recordings on one clock. `upload_timestamp` is ingest time.
- Deploy with `scripts/deploy.sh` only, into this team's namespace, at Ingress path `/app`.
