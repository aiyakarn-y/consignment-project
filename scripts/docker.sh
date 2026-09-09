#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v docker >/dev/null 2>&1; then
  echo 'Docker Engine with Compose v2 is required. Native Local: npm start' >&2
  exit 1
fi
export CONSIGN_DOCKER_UID="${CONSIGN_DOCKER_UID:-$(id -u)}"
export CONSIGN_DOCKER_GID="${CONSIGN_DOCKER_GID:-$(id -g)}"
case "${1:-up}" in
  up)
    mkdir -p data/local
    docker compose config --quiet
    exec docker compose up --build
    ;;
  down) exec docker compose down ;;
  *) echo 'Usage: bash scripts/docker.sh up|down' >&2; exit 2 ;;
esac
