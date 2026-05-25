#!/usr/bin/env bash
set -euo pipefail

# Local Docker verification script for Quetie_mbg
# Builds image, starts container, waits for /health, tails logs.

PORT=${PORT:-8000}
IMAGE=quetie_mbg:local
CONTAINER=quetie_mbg_local
TIMEOUT=${TIMEOUT:-60}

echo "[verify] Building Docker image: ${IMAGE}"
docker build -t ${IMAGE} .

echo "[verify] Removing existing container (if any): ${CONTAINER}"
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  docker rm -f ${CONTAINER} || true
fi

echo "[verify] Starting container"
docker run --env-file .env -d --name ${CONTAINER} -p ${PORT}:8000 ${IMAGE}

echo "[verify] Waiting for /health on http://localhost:${PORT} (timeout ${TIMEOUT}s)"
SECS=0
while [ $SECS -lt $TIMEOUT ]; do
  if curl -sS "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    echo "[verify] Health endpoint responded:" 
    if command -v jq >/dev/null 2>&1; then
      curl -s "http://localhost:${PORT}/health" | jq '.' || true
    else
      curl -s "http://localhost:${PORT}/health" || true
    fi
    echo "[verify] Startup successful. Tailing logs (press Ctrl+C to exit)..."
    docker logs -f --tail 200 ${CONTAINER}
    exit 0
  fi
  sleep 2
  SECS=$((SECS+2))
done

echo "[verify][error] Health endpoint did not respond within ${TIMEOUT}s"
echo "[verify] Last container logs:"
docker logs --tail 200 ${CONTAINER} || true
exit 2
