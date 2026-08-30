"""Deterministic redaction engine detectors (issue #150, S2)."""

from app.services.redaction_engine import (
    RedactedContent,
    build_redaction_findings,
    redact_structured_output,
    redact_text,
)

# Deterministic test identifiers with VALID checksums.
VALID_IBAN = "DE89370400440532013000"
VALID_PAN = "4111111111111111"
INVALID_LUHN = "4111111111111112"


def test_redacts_valid_iban_and_leaves_invalid_shapes() -> None:
    result = redact_text(f"Transfer to {VALID_IBAN} settled.")
    assert result.text == "Transfer to [REDACTED:iban] settled."
    assert result.counts == {"iban": 1}

    # Shape matches, mod-97 fails: not an IBAN, must remain untouched.
    broken = VALID_IBAN[:-1] + "1"
    untouched = redact_text(f"Reference {broken} recorded.")
    assert untouched.counts == {}
    assert broken in untouched.text


def test_redacts_luhn_valid_pans_only() -> None:
    result = redact_text(f"Card {VALID_PAN} charged; ref {INVALID_LUHN}.")
    assert result.counts == {"card_pan": 1}
    assert "[REDACTED:card_pan]" in result.text
    assert INVALID_LUHN in result.text

    separated = redact_text("PAN 4111 1111 1111 1111 on file.")
    assert separated.counts == {"card_pan": 1}


def test_redacts_email_and_plus_prefixed_phone_only() -> None:
    result = redact_text("Reach ops.user@lotus.test or +41 44 123 45 67.")
    assert result.counts == {"email": 1, "phone": 1}
    assert "[REDACTED:email]" in result.text
    assert "[REDACTED:phone]" in result.text

    # Bare digit runs are portfolio data, never phones.
    amounts = redact_text("Position 12345678 grew by 1234567.89.")
    assert amounts.counts == {}


def test_redacts_caller_declared_client_identifiers_literally() -> None:
    result = redact_text(
        "Client ACME-PRIVATE-0042 approved the mandate for ACME-PRIVATE-0042.",
        client_identifiers=["ACME-PRIVATE-0042"],
    )
    assert result.counts == {"client_identifier": 2}
    assert "ACME-PRIVATE-0042" not in result.text


def test_allowlisted_types_are_skipped_per_task_only() -> None:
    result = redact_text(
        f"Card {VALID_PAN} and mail ops.user@lotus.test.",
        allowlisted_types=["card_pan"],
    )
    assert result.counts == {"email": 1}
    assert VALID_PAN in result.text


def test_redaction_is_deterministic_for_identical_input() -> None:
    text = f"IBAN {VALID_IBAN}, card {VALID_PAN}, mail ops.user@lotus.test, tel +12025550175."
    first = redact_text(text)
    second = redact_text(text)
    assert first == second
    assert isinstance(first, RedactedContent)
    assert first.counts == {"iban": 1, "card_pan": 1, "email": 1, "phone": 1}


def test_structured_output_walk_covers_nested_string_leaves() -> None:
    payload: dict[str, object] = {
        "summary": f"Contact ops.user@lotus.test about {VALID_IBAN}.",
        "nested": {"notes": [f"Card {VALID_PAN}.", 42, None]},
        "count": 3,
    }
    redacted, counts = redact_structured_output(payload)
    assert counts == {"email": 1, "iban": 1, "card_pan": 1}
    assert "[REDACTED:email]" in str(redacted["summary"])
    nested = redacted["nested"]
    assert isinstance(nested, dict)
    assert "[REDACTED:card_pan]" in str(nested["notes"][0])
    assert nested["notes"][1] == 42
    assert redacted["count"] == 3


def test_findings_are_sorted_type_count_pairs_without_values() -> None:
    findings = build_redaction_findings({"email": 2, "card_pan": 1, "phone": 0})
    assert [(item.finding_type, item.count) for item in findings] == [
        ("card_pan", 1),
        ("email", 2),
    ]
