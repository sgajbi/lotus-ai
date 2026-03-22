from fastapi import FastAPI, Response, status
from prometheus_fastapi_instrumentator import Instrumentator
from app.middleware.correlation import CorrelationIdMiddleware

SERVICE_NAME = "lotus-ai"
SERVICE_VERSION = "0.1.0"
ROUNDING_POLICY_VERSION = "v1"

app = FastAPI(
    title=SERVICE_NAME,
    version=SERVICE_VERSION,
    description=(
        "Shared AI platform service for Lotus applications. "
        "This service owns reusable AI infrastructure and governed task execution, "
        "not domain business truth."
    ),
)
app.add_middleware(CorrelationIdMiddleware, service_name=SERVICE_NAME)
Instrumentator().instrument(app).expose(app)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/health/live")
async def health_live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
async def health_ready(response: Response) -> dict[str, str]:
    if bool(getattr(app.state, "is_draining", False)):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "draining"}
    return {"status": "ready"}


@app.get("/metadata")
async def metadata() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "roundingPolicyVersion": ROUNDING_POLICY_VERSION,
    }


@app.get("/")
async def root() -> dict[str, object]:
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "capabilityAreas": [
            "llm_gateway",
            "prompt_registry",
            "retrieval",
            "safety",
            "evals",
            "task_apis",
        ],
    }
