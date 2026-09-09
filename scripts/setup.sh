#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm --prefix frontend ci
if [[ ! -f .env ]]; then cp .env.example .env; fi
.venv/bin/python -c 'from backend.config import DATA; from backend.storage import LocalFileStore; LocalFileStore(DATA).prepare()'
npm run build
