#!/bin/bash
echo "Running database migrations..."
uvx pdm run alembic upgrade head

echo "Starting FastAPI ..."
uvx pdm run uvicorn backend.api.app:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1 \
  --loop uvloop \
  --http httptools