#!/bin/sh
# Container entrypoint: apply migrations (retrying until the database is ready),
# then start the API server.
set -e

echo "Applying database migrations..."
attempt=0
until alembic upgrade head; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 20 ]; then
        echo "Migrations failed after $attempt attempts; giving up." >&2
        exit 1
    fi
    echo "Database not ready (attempt $attempt); retrying in 2s..."
    sleep 2
done

echo "Starting Bookmarks API on http://0.0.0.0:8000 ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
