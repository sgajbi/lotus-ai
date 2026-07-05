from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProblemDetails(BaseModel):
    type: str = Field(description="Stable Lotus AI problem type URI.")
    title: str = Field(description="Short stable summary of the failure class.")
    status: int = Field(description="HTTP status code returned for the failure.")
    detail: str = Field(description="Bounded caller-safe diagnostic detail.")
    error_code: str = Field(description="Stable Lotus AI application error code.")
    correlation_id: str = Field(description="Correlation identifier for support tracing.")
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Optional source-safe metadata for automated support tooling.",
    )


PROBLEM_DETAILS_RESPONSE_DESCRIPTION = "Problem-details error returned by lotus-ai."


def problem_response(description: str = PROBLEM_DETAILS_RESPONSE_DESCRIPTION) -> dict[str, Any]:
    return {
        "model": ProblemDetails,
        "description": description,
        "content": {
            "application/problem+json": {
                "example": {
                    "type": "https://lotus.ai/problems/validation-failed",
                    "title": "Request validation failed",
                    "status": 422,
                    "detail": "Request validation failed.",
                    "error_code": "LOTUS_AI_VALIDATION_FAILED",
                    "correlation_id": "corr-example",
                    "metadata": {"validation_error_count": 1},
                }
            }
        },
    }


COMMON_PROBLEM_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: problem_response("Request rejected by lotus-ai boundary controls."),
    403: problem_response("Caller or origin is not authorized for this request."),
    404: problem_response("Requested lotus-ai resource was not found."),
    409: problem_response("Request conflicts with the current lotus-ai runtime posture."),
    413: problem_response("Request body exceeds the configured lotus-ai boundary limit."),
    422: problem_response("Request validation failed."),
    429: problem_response("Request exceeds lotus-ai admission or rate limits."),
    500: problem_response("Unexpected lotus-ai server error."),
    503: problem_response("A lotus-ai runtime dependency is unavailable."),
}
