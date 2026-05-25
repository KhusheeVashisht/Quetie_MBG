#!/usr/bin/env bash
set -euo pipefail

# Lightweight Docker verification script for Quetie_mbg
# - Builds the image
# - Starts the container (python main.py --mode all)
# - Waits for /health to respond
# - Tails logs
# - Optionally removes old containers before starting

IMAGE="quetie_mbg:local"
CONTAINER="quetie_mbg_local"
PORT="${PORT:-8000}"
ENVFILE=".env"
MAX_WAIT=${MAX_WAIT:-60}

echo "== Quetie_mbg Docker verification script =="

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed or not in PATH"
  exit 2
fi

echo "Cleaning previous container (if any): ${CONTAINER}"
if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER}$"; then
  docker rm -f "${CONTAINER}" >/dev/null || true
fi

echo "Building Docker image: ${IMAGE}"
docker build -t "${IMAGE}" .

RUN_ARGS=(docker run -d -p "${PORT}:8000" --name "${CONTAINER}")

if [ -f "${ENVFILE}" ]; then
  echo "Using env file: ${ENVFILE}"
  RUN_ARGS+=(--env-file "${ENVFILE}")
else
  echo "Warning: ${ENVFILE} not found. Proceeding without env file."
fi

RUN_ARGS+=("${IMAGE}")

echo "Starting container..."
"${RUN_ARGS[@]}"

echo "Waiting up to ${MAX_WAIT}s for /health..."
SUCCESS=0
for i in $(seq 1 ${MAX_WAIT}); do
  OUT=$(curl -sS --max-time 2 "http://127.0.0.1:${PORT}/health" 2>/dev/null || true)
  if [ -n "${OUT}" ]; then
    echo
    echo "Health response:" 
    if command -v jq >/dev/null 2>&1; then
      echo "${OUT}" | jq
    else
      echo "${OUT}"
    fi
    SUCCESS=1
    break
  fi
  echo -n "."
  sleep 1
done

if [ "${SUCCESS}" -ne 1 ]; then
  echo
  echo "Health check failed after ${MAX_WAIT}s. Showing last container logs:"
  docker logs --tail 200 "${CONTAINER}" || true
  exit 1
fi

echo
echo "Application started successfully. Tailing logs (Ctrl+C to stop)."
echo "To remove the test container: docker rm -f ${CONTAINER}"
docker logs -f "${CONTAINER}"
