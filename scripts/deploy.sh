#!/usr/bin/env bash
# Deploy Sherlocked to the team namespace at Ingress path /app.
# Follows .cursor/skills/deployment/deploy-app-no-registry. Does not print secrets.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="${HOME}/.local/node/bin:${HOME}/.local/bin:${PATH}"

mapfile -t TEAM_CONFIGS < <(find /config -maxdepth 1 -type f -name '*.config' | sort)
if [[ ${#TEAM_CONFIGS[@]} -ne 1 ]]; then
  echo "expected exactly one /config/*.config" >&2
  exit 1
fi
TEAM_CONFIG="${TEAM_CONFIGS[0]}"
USERNAME="$(grep '^USERNAME=' "$TEAM_CONFIG" | cut -d= -f2-)"
INGRESS_URL="$(grep '^INGRESS_URL=' "$TEAM_CONFIG" | cut -d= -f2-)"
PASSWORD="$(grep '^PASSWORD=' "$TEAM_CONFIG" | cut -d= -f2-)"
# W&B credentials are process environment variables, not keys in the team config.
WANDB_API_KEY="${WANDB_API_KEY:-}"
WANDB_TEAM="${WANDB_TEAM:-}"
WANDB_PROJECT="${WANDB_PROJECT:-}"
NS="$USERNAME"
export KUBECONFIG="/config/${NS}-k8s.yaml"
TEAM_N="${USERNAME#team-}"
APP_HOST="video-lab-team-${TEAM_N}.cosmos.vastdata.com"
APP_NAME="sherlocked"
APP_PORT=8080

echo "Building frontend with base /app/"
(
  cd "$ROOT/frontend"
  VITE_BASE=/app/ npm run build
)

BUNDLE="$(mktemp -d)"
mkdir -p "$BUNDLE/stage"
mkdir -p "$BUNDLE/stage/frontend"
cp -a "$ROOT/backend" "$BUNDLE/stage/backend"
cp -a "$ROOT/frontend/dist" "$BUNDLE/stage/frontend/dist"
find "$BUNDLE/stage" -type d -name '__pycache__' -prune -exec rm -rf {} +
find "$BUNDLE/stage" -type d -name 'tests' -prune -exec rm -rf {} +
tar -C "$BUNDLE/stage" -czf "$BUNDLE/app.tar.gz" backend frontend
cp "$ROOT/backend/requirements.txt" "$BUNDLE/requirements.txt"
cat > "$BUNDLE/start.sh" << 'EOF'
#!/bin/bash
set -euo pipefail
mkdir -p /opt/sherlocked
tar -xzf /code/app.tar.gz -C /opt/sherlocked
cd /opt/sherlocked
pip install --no-cache-dir -q -r backend/requirements.txt
export VIDEO_PROVIDER=vast
export REASONING_PROVIDER="${REASONING_PROVIDER:-wandb}"
export SHERLOCKED_DB=/tmp/sherlocked.db
exec python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8080}"
EOF
chmod 644 "$BUNDLE/start.sh"

BYTES=$(wc -c < "$BUNDLE/app.tar.gz")
echo "bundle_bytes ${BYTES}"
if [[ "$BYTES" -gt 900000 ]]; then
  echo "bundle is over 900000 bytes; ConfigMap limit is about 1 MiB" >&2
  exit 1
fi

# The public ingress host does not resolve inside the cluster. The pod calls the
# team's video-backend Service on the cluster network instead.
if kubectl -n "$NS" get svc video-backend-service >/dev/null 2>&1; then
  VSS_INTERNAL="http://video-backend-service:8000"
else
  VSS_INTERNAL="$INGRESS_URL"
fi

if [[ -z "${WANDB_API_KEY}" ]]; then
  _wb="$(kubectl -n "$NS" get secret "${APP_NAME}-vss-creds" -o json 2>/dev/null | python3 -c '
import json, sys, base64, shlex
raw = sys.stdin.read().strip()
if not raw:
    raise SystemExit(0)
data = json.loads(raw).get("data") or {}
for key in ("WANDB_API_KEY", "WANDB_TEAM", "WANDB_PROJECT"):
    blob = data.get(key)
    if not blob:
        continue
    value = base64.b64decode(blob).decode()
    print(f"{key}={shlex.quote(value)}")
' || true)"
  if [[ -n "${_wb}" ]]; then
    eval "${_wb}"
  fi
  unset _wb
fi

echo "Applying ConfigMap, Secret, Deployment, Service, Ingress in ${NS}"
kubectl -n "$NS" create configmap "${APP_NAME}-code" \
  --from-file="$BUNDLE/requirements.txt" \
  --from-file="$BUNDLE/start.sh" \
  --from-file="$BUNDLE/app.tar.gz" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$NS" create secret generic "${APP_NAME}-vss-creds" \
  --from-literal=VSS_URL="$VSS_INTERNAL" \
  --from-literal=VSS_USERNAME="$USERNAME" \
  --from-literal=VSS_PASSWORD="$PASSWORD" \
  --from-literal=WANDB_API_KEY="${WANDB_API_KEY:-}" \
  --from-literal=WANDB_TEAM="${WANDB_TEAM:-}" \
  --from-literal=WANDB_PROJECT="${WANDB_PROJECT:-}" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl -n "$NS" apply -f - << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${APP_NAME}
  labels:
    app: ${APP_NAME}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${APP_NAME}
  template:
    metadata:
      labels:
        app: ${APP_NAME}
    spec:
      containers:
      - name: app
        image: python:3.12-slim
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: ${APP_PORT}
        env:
        - name: PORT
          value: "${APP_PORT}"
        - name: VSS_URL
          valueFrom:
            secretKeyRef:
              name: ${APP_NAME}-vss-creds
              key: VSS_URL
        - name: VSS_USERNAME
          valueFrom:
            secretKeyRef:
              name: ${APP_NAME}-vss-creds
              key: VSS_USERNAME
        - name: VSS_PASSWORD
          valueFrom:
            secretKeyRef:
              name: ${APP_NAME}-vss-creds
              key: VSS_PASSWORD
        - name: WANDB_API_KEY
          valueFrom:
            secretKeyRef:
              name: ${APP_NAME}-vss-creds
              key: WANDB_API_KEY
        - name: WANDB_TEAM
          valueFrom:
            secretKeyRef:
              name: ${APP_NAME}-vss-creds
              key: WANDB_TEAM
        - name: WANDB_PROJECT
          valueFrom:
            secretKeyRef:
              name: ${APP_NAME}-vss-creds
              key: WANDB_PROJECT
        volumeMounts:
        - name: code
          mountPath: /code
        workingDir: /code
        command: ["bash", "/code/start.sh"]
        readinessProbe:
          httpGet:
            path: /health
            port: ${APP_PORT}
          initialDelaySeconds: 25
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 18
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            memory: 768Mi
      volumes:
      - name: code
        configMap:
          name: ${APP_NAME}-code
---
apiVersion: v1
kind: Service
metadata:
  name: ${APP_NAME}
  labels:
    app: ${APP_NAME}
spec:
  selector:
    app: ${APP_NAME}
  ports:
  - name: http
    port: 80
    targetPort: ${APP_PORT}
  type: ClusterIP
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ${APP_NAME}
  labels:
    app: ${APP_NAME}
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /\$2
    nginx.ingress.kubernetes.io/proxy-read-timeout: "180"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "180"
spec:
  ingressClassName: nginx
  rules:
  - host: ${APP_HOST}
    http:
      paths:
      - path: /app(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: ${APP_NAME}
            port:
              number: 80
EOF

kubectl -n "$NS" rollout restart "deploy/${APP_NAME}"
kubectl -n "$NS" rollout status "deploy/${APP_NAME}" --timeout=180s
kubectl -n "$NS" get pods,svc,ingress -l "app=${APP_NAME}"
echo "ingress_check"
curl -sS -o /dev/null -w "app_root %{http_code}\n" "http://${APP_HOST}/app/" || true
curl -sS -o /dev/null -w "health %{http_code}\n" "http://${APP_HOST}/app/health" || true
rm -rf "$BUNDLE"
echo "Open https://workshop.thecosmoslabs.com and click the App button."
