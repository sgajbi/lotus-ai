#!/bin/sh
set -eu

python -m app.operations.alembic_bootstrap
python -m alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8140
