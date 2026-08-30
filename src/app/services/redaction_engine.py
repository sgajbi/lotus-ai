"""Deterministic runtime redaction engine (issue #150, S2).

Screens generated content - the response message (which becomes the audit
result preview), structured-output string leaves, and the audited context
summary - for sensitive identifiers before persistence and egress.

Deterministic by construction: detectors are ordered, purely pattern-based
(with checksum validation where the format defines one), and identical
input always yields identical findings and identical redacted output, so
replay comparisons stay valid. Findings are recorded as detector-class
counts only - never the matched values.

Detector boundaries, chosen for a numeric-heavy finance domain:
- ``iban``: ISO 13616 shape with a passing mod-97 check.
- ``card_pan``: 13-19 digit runs (single space/dash separators allowed)
  with a passing Luhn check.
- ``email``: conservative RFC-adjacent mailbox pattern.
- ``phone``: requires a leading ``+`` and 8-15 digits - bare digit runs
  are never treated as phone numbers, because portfolio data is full of
  them.
- ``client_identifier``: literal caller-policy-declared identifiers.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.contracts.safety import RedactionFindingDescriptor

REDACTION_MODE_OBSERVE = "observe"
REDACTION_MODE_ENFORCE = "enforce"

_IBAN_PATTERN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_PAN_PATTERN = re.compile(r"(?<![\dA-Za-z])(?:\d[ -]?){12,18}\d(?![\dA-Za-z])")
_EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_PATTERN = re.compile(r"(?<![\dA-Za-z])\+\d(?:[\s().-]?\d){7,14}(?![\dA-Za-z])")


@dataclass(frozen=True)
class RedactedContent:
    text: str
    counts: dict[str, int]


def _iban_is_valid(candidate: str) -> bool:
    rearranged = candidate[4:] + candidate[:4]
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(numeric) % 97 == 1


def _luhn_is_valid(digits: str) -> bool:
    total = 0
    for index, ch in enumerate(reversed(digits)):
        value = int(ch)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _redact_iban(text: str, counts: dict[str, int]) -> str:
    def _replace(match: re.Match[str]) -> str:
        if not _iban_is_valid(match.group(0)):
            return match.group(0)
        counts["iban"] = counts.get("iban", 0) + 1
        return "[REDACTED:iban]"

    return _IBAN_PATTERN.sub(_replace, text)


def _redact_card_pan(text: str, counts: dict[str, int]) -> str:
    def _replace(match: re.Match[str]) -> str:
        digits = re.sub(r"[ -]", "", match.group(0))
        if not (13 <= len(digits) <= 19) or not _luhn_is_valid(digits):
            return match.group(0)
        counts["card_pan"] = counts.get("card_pan", 0) + 1
        return "[REDACTED:card_pan]"

    return _PAN_PATTERN.sub(_replace, text)


def _redact_email(text: str, counts: dict[str, int]) -> str:
    def _replace(match: re.Match[str]) -> str:
        counts["email"] = counts.get("email", 0) + 1
        return "[REDACTED:email]"

    return _EMAIL_PATTERN.sub(_replace, text)


def _redact_phone(text: str, counts: dict[str, int]) -> str:
    def _replace(match: re.Match[str]) -> str:
        counts["phone"] = counts.get("phone", 0) + 1
        return "[REDACTED:phone]"

    return _PHONE_PATTERN.sub(_replace, text)


_DETECTOR_ORDER: tuple[tuple[str, object], ...] = (
    ("iban", _redact_iban),
    ("card_pan", _redact_card_pan),
    ("email", _redact_email),
    ("phone", _redact_phone),
)


def redact_text(
    text: str,
    *,
    client_identifiers: Iterable[str] = (),
    allowlisted_types: Iterable[str] = (),
) -> RedactedContent:
    allowlist = set(allowlisted_types)
    counts: dict[str, int] = {}
    redacted = text
    for detector_type, detector in _DETECTOR_ORDER:
        if detector_type in allowlist:
            continue
        redacted = detector(redacted, counts)  # type: ignore[operator]
    if "client_identifier" not in allowlist:
        for identifier in sorted(set(client_identifiers)):
            if not identifier:
                continue
            occurrences = redacted.count(identifier)
            if occurrences:
                counts["client_identifier"] = counts.get("client_identifier", 0) + occurrences
                redacted = redacted.replace(identifier, "[REDACTED:client_identifier]")
    return RedactedContent(text=redacted, counts=counts)


def redact_structured_output(
    payload: dict[str, object],
    *,
    client_identifiers: Iterable[str] = (),
    allowlisted_types: Iterable[str] = (),
) -> tuple[dict[str, object], dict[str, int]]:
    counts: dict[str, int] = {}

    def _walk(value: object) -> object:
        if isinstance(value, str):
            result = redact_text(
                value,
                client_identifiers=client_identifiers,
                allowlisted_types=allowlisted_types,
            )
            _merge_counts(counts, result.counts)
            return result.text
        if isinstance(value, dict):
            return {key: _walk(item) for key, item in value.items()}
        if isinstance(value, list):
            return [_walk(item) for item in value]
        return value

    return {key: _walk(item) for key, item in payload.items()}, counts


def _merge_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + value


def build_redaction_findings(counts: dict[str, int]) -> list[RedactionFindingDescriptor]:
    return [
        RedactionFindingDescriptor(finding_type=finding_type, count=count)
        for finding_type, count in sorted(counts.items())
        if count > 0
    ]
