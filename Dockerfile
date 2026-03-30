# Build stage for Frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# Final stage
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1

# Install Caddy
RUN apt-get update && apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl \
    && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg \
    && curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list \
    && apt-get update \
    && apt-get install -y caddy \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Setup Backend
COPY backend/pyproject.toml backend/uv.lock ./
COPY backend/ .
RUN uv sync
RUN uv run python -m nltk.downloader cmudict
# Copy Frontend Build
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Copy Configs
COPY Caddyfile /etc/caddy/Caddyfile
COPY entrypoint.sh /start.sh
RUN chmod +x /start.sh

# Copy .env if exists
COPY .env* ./

# Copy Data
# COPY data/ ./data/
# ENV TTDS_DATA_FILE=/app/data/songs_5000.csv
# ENV TTDS_INDEX_FILE=/app/data/songsIndex.txt

ENV PORT=8080
EXPOSE 8080

CMD ["/start.sh"]
