"""Monetary float-usage guard.

Deterministic financial truth must not be computed with binary floats. This
guard flags ``float(`` usage on lines that look monetary (by keyword hint)
under ``src/``.

A line that uses float legitimately - display formatting, leak-detection
comparisons against caller-supplied values, embedding vectors that merely
match a hint word - carries an inline waiver with a recorded reason::

    allowed = [float(v) for v in values]  # monetary-float-ok: display-only comparison

A waiver without a reason is itself a violation: every exception is
review-visible at the site it excuses, never in a central list.
"""

from __future__ import annotations

import sys
from pathlib import Path

MONETARY_HINTS = ("amount", "value", "price", "cost", "pnl", "market_value", "fx_rate")
WAIVER_MARKER = "# monetary-float-ok:"


def likely_monetary(line: str) -> bool:
    low = line.lower()
    return any(token in low for token in MONETARY_HINTS)


def _line_violation(line: str) -> str | None:
    if "float(" not in line or not likely_monetary(line):
        return None
    if WAIVER_MARKER in line:
        reason = line.split(WAIVER_MARKER, 1)[1].strip()
        if reason:
            return None
        return "monetary float waiver has no reason"
    return "monetary float usage detected"


def main(root: str = "src") -> int:
    violations: list[str] = []
    for path in sorted(Path(root).rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for idx, line in enumerate(text.splitlines(), start=1):
            finding = _line_violation(line)
            if finding is not None:
                violations.append(f"{path}:{idx}: {finding}")
    if violations:
        print("\n".join(violations))
        return 1
    print("Monetary float guard passed")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "src"))
