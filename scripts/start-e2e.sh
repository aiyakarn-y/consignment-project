#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../frontend"
npm run build
export HOSTNAME=127.0.0.1 PORT=3118
exec node "${CONSIGN_NEXT_DIR:-.next}/standalone/server.js"
