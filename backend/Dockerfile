# Stage 1: build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir -e .

RUN playwright install chromium && playwright install-deps chromium

COPY backend/ .

# Copy built React app into FastAPI's static directory
COPY --from=frontend-build /frontend/dist /app/app/static

EXPOSE 8000
