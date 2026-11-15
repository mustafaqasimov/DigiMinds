# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_PATH=/app/data/crisis.db

WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && groupadd --gid 10001 digiminds \
    && useradd --uid 10001 --gid digiminds --create-home digiminds \
    && mkdir -p /app/data \
    && chown digiminds:digiminds /app/data

# Models and optional inference packages are intentionally not in the core image.
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY speech/ ./speech/
COPY vision/ ./vision/

USER 10001:10001
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=6 \
    CMD python -c "import json, urllib.request; r=urllib.request.build_opener(urllib.request.ProxyHandler({})).open('http://127.0.0.1:3000/api/health', timeout=2); assert json.load(r)['ok'] is True"

# SQLite, admission quotas and circuit state currently require ONE app worker.
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "3000", "--workers", "1", "--no-proxy-headers", "--no-access-log"]
