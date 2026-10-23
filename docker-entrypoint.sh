#!/bin/sh
set -e
# First boot: optional demo data and an optional admin from ADMIN_EMAIL / ADMIN_NAME / ADMIN_PASSWORD.
if [ "$SEED_DEMO" = "1" ]; then python -m app.cli seed-demo || true; fi
if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then python -m app.cli create-admin || true; fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips "*"
