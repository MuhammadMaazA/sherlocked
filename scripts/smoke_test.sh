#!/usr/bin/env bash
# Hit a running Sherlocked API. Does not print tokens.
set -euo pipefail
BASE="${1:-http://127.0.0.1:8000}"
echo "probe $(curl -fsS "$BASE/health")"
python3 - "$BASE" << 'PY'
import json, sys, urllib.request
base = sys.argv[1]
def call(method, path, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method=method)
    if body is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())
health = call("GET", "/api/health")
print("provider", health.get("provider"), "synthetic", health.get("synthetic"), "status", health.get("status"))
search = call("POST", "/api/videos/search", {"query": "person near a forklift", "camera_id": "sdg_warehouse_cam-2", "top_k": 2})
print("hits", len(search.get("results") or []), "synthetic", search.get("synthetic"))
if search.get("results"):
    print("camera", search["results"][0].get("camera_id"), "score", search["results"][0].get("retrieval_score"))
PY
