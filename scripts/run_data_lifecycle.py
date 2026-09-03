"""Apply the data-retention policy once and print the evidence (issue #158, S2a).

Usage: python scripts/run_data_lifecycle.py [actor]

The actor lands on every deletion-evidence row; default names the scheduled
job identity so an operator-invoked run is distinguishable by passing their
own identity.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict


def main() -> int:
    from app.services.data_lifecycle_engine import run_data_lifecycle

    actor = sys.argv[1] if len(sys.argv) > 1 else "lotus-ai.data-lifecycle-job"
    report = run_data_lifecycle(actor=actor)
    print(json.dumps(asdict(report), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
