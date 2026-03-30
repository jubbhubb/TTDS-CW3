#!/bin/sh
set -e

# Start the Python backend in the background
echo "Starting Python backend..."
uv run gunicorn -w 1 -b 127.0.0.1:5000 --timeout 120 --log-level debug --access-logfile - --error-logfile - "api:create_app()" &

# Start Caddy in the foreground
echo "Starting Caddy..."
caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
