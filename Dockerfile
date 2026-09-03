# Fleet supply-chain baseline (issue #155): digest-pinned base, two stages,
# hash-verified locked dependencies, non-root runtime, HEALTHCHECK. The
# audited dependency set is the deployed set; refresh the digest deliberately
# in a commit that says why.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea AS builder

WORKDIR /build
COPY requirements.lock.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes -r requirements.lock.txt

FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY alembic.ini ./
COPY alembic ./alembic
COPY contracts ./contracts
COPY src ./src
# Runtime-read data manifests only - the async job registry and eval
# fixture/run registries load these; prose docs stay out of the image.
COPY docs/async ./docs/async
COPY docs/evals ./docs/evals
COPY scripts/docker ./scripts/docker
RUN sed -i 's/\r$//' scripts/docker/start-api.sh scripts/docker/start-worker.sh \
    && chmod +x scripts/docker/start-api.sh scripts/docker/start-worker.sh \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src
USER app

EXPOSE 8140
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8140/health/live', timeout=4)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8140"]
