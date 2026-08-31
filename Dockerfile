FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY alembic.ini ./
COPY alembic ./alembic
COPY contracts ./contracts
COPY docs ./docs
COPY src ./src
COPY scripts ./scripts
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e ".[dev]"
RUN sed -i 's/\r$//' scripts/docker/start-api.sh scripts/docker/start-worker.sh \
    && chmod +x scripts/docker/start-api.sh scripts/docker/start-worker.sh

EXPOSE 8140
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8140"]
