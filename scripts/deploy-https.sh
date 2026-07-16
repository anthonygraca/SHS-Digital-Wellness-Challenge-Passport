#!/usr/bin/env bash
#
# One-shot HTTPS deploy for the EC2 box (or any non-localhost host).
#
# Why: the QR check-in scanner uses the browser camera (getUserMedia), and — like
# the PWA service worker — the browser only exposes it in a *secure context*:
# HTTPS, or localhost. Served over plain HTTP from a public host (e.g.
# http://35.165.46.208) the browser disables the camera and never prompts. This
# script builds the SPA and serves it + the API over HTTPS from one uvicorn
# process, using a self-signed cert (click through the one-time browser warning).
#
# Usage (from the repo root, on the server) — no sudo needed on the default port:
#   scripts/deploy-https.sh                  # serve on :8443, visit https://<host>:8443
#   sudo HTTPS_PORT=443 scripts/deploy-https.sh   # serve on :443 (privileged port)
#
# Remember to open the chosen port for inbound HTTPS in the EC2 security group,
# then browse to https://<host>:<port> (note https).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HTTPS_PORT="${HTTPS_PORT:-8443}"
HTTPS_HOST="${HTTPS_HOST:-0.0.0.0}"
CERT_DIR="$ROOT/certs"

# Skip install when deps already exist — the box is already provisioned, and
# re-running `make install` under sudo can chown a user-owned venv to root.
if [[ -x backend/.venv/bin/uvicorn && -d frontend/node_modules ]]; then
  echo "==> Deps present, skipping install"
else
  echo "==> Installing deps (backend venv + frontend)"
  make install
fi

echo "==> Building the frontend (SPA + PWA)"
make build

if [[ ! -f "$CERT_DIR/cert.pem" || ! -f "$CERT_DIR/key.pem" ]]; then
  echo "==> Generating self-signed cert into certs/"
  mkdir -p "$CERT_DIR"
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
    -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" -subj "/CN=$HTTPS_HOST"
fi

echo "==> Serving SPA + API over HTTPS on $HTTPS_HOST:$HTTPS_PORT"
echo "    Open inbound $HTTPS_PORT in the EC2 security group, then visit:"
echo "      https://<this-host>${HTTPS_PORT:+:$HTTPS_PORT}"
echo "    (Self-signed: the browser warns once — Advanced -> Proceed.)"
exec backend/.venv/bin/uvicorn app.main:app \
  --app-dir backend \
  --host "$HTTPS_HOST" --port "$HTTPS_PORT" \
  --ssl-keyfile "$CERT_DIR/key.pem" --ssl-certfile "$CERT_DIR/cert.pem"
