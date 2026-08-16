#!/usr/bin/env bash
set -euo pipefail

# Configure your own remote build host, e.g.
#   export REMOTE_HOST=user@host
#   export REMOTE_DIR=/path/on/remote/BSMScanner
REMOTE_HOST="${REMOTE_HOST:?set REMOTE_HOST, e.g. export REMOTE_HOST=user@host}"
REMOTE_DIR="${REMOTE_DIR:?set REMOTE_DIR, e.g. export REMOTE_DIR=/home/you/BSMScanner}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ssh "${REMOTE_HOST}" "mkdir -p '${REMOTE_DIR}'"

rsync -az --delete \
  --exclude '.venv/' \
  --exclude 'build/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  "${ROOT_DIR}/" "${REMOTE_HOST}:${REMOTE_DIR}/"

echo "Synced ${ROOT_DIR} -> ${REMOTE_HOST}:${REMOTE_DIR}"

