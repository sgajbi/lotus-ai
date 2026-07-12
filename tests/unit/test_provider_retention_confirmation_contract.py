import json
from pathlib import Path

from app.main import app

ROOT = Path(__file__).resolve().parents[2]


def test_provider_retention_contract_matches_openapi_and_authority_boundary() -> None:
    contract = json.loads(
        (
            ROOT
            / "contracts"
            / "provider-retention-confirmations"
            / "lotus-ai-provider-retention-confirmation.v1.json"
        ).read_text(encoding="utf-8")
    )
    operation = app.openapi()["paths"][contract["route"]]["post"]

    assert contract["method"] == "POST"
    assert contract["approved_recorder"] == "lotus-ai-provider-operations"
    assert contract["approved_consumer"] == "lotus-idea"
    assert contract["signing"]["curve"] == "Ed25519"
    assert contract["supportability_status"] == "not_certified"
    assert "ProviderRetentionConfirmationRequest" in str(operation["requestBody"])
    assert "ProviderRetentionConfirmationEnvelope" in str(operation["responses"]["201"])
    assert {"404", "409", "422", "503"}.issubset(operation["responses"])
