#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd "$(dirname "$0")/.." && pwd)"
exec "$project_root/.venv/bin/python" "$project_root/scripts/local.py" stop
