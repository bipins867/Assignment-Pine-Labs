#!/bin/bash
set -e

echo "==> Waiting for MySQL to be ready..."
# Simple wait loop — retries for up to 30 seconds
for i in $(seq 1 30); do
    python -c "
from app.core.config import get_settings
from sqlalchemy import create_engine, text
s = get_settings()
e = create_engine(s.DATABASE_URL)
with e.connect() as c:
    c.execute(text('SELECT 1'))
print('MySQL is ready!')
" 2>/dev/null && break
    echo "  Waiting for MySQL... ($i/30)"
    sleep 1
done

echo "==> Running Alembic migrations..."
alembic upgrade head

echo "==> Starting FastAPI application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
