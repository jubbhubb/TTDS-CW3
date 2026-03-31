#!/bin/sh
set -e

echo "Starting Python backend with Gunicorn..."
# We use --daemon to ensure it stays in the background properly 
# or use & and wait. 
uv run gunicorn -w 1 -b 127.0.0.1:5000 --timeout 120 "api:create_app()" &

echo "Starting Caddy..."
# Caddy must stay in the FOREGROUND. If Caddy stops, the container stops.
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile