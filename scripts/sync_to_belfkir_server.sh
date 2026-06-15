#!/usr/bin/env bash
set -euo pipefail

REMOTE_HOST="${REMOTE_HOST:-mohamed@belfkir-server}"
REMOTE_DIR="${REMOTE_DIR:-/home/mohamed/HEP/BSMScanner}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

ssh "${REMOTE_HOST}" "mkdir -p '${REMOTE_DIR}'"

rsync -az --delete \
  --exclude '.venv/' \
  --exclude 'build/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  "${ROOT_DIR}/" "${REMOTE_HOST}:${REMOTE_DIR}/"

echo "Synced ${ROOT_DIR} -> ${REMOTE_HOST}:${REMOTE_DIR}"

