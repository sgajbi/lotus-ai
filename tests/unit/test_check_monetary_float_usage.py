"""Monetary float guard behaviour (issue #199)."""

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_guard() -> ModuleType:
    script_path = Path("scripts") / "check_monetary_float_usage.py"
    spec = importlib.util.spec_from_file_location("check_monetary_float_usage", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_monetary_guard_passes_on_current_src() -> None:
    guard = _load_guard()
    assert guard.main("src") == 0


def test_monetary_guard_flags_unwaived_usage_one_per_line(tmp_path: Path, capsys: object) -> None:
    guard = _load_guard()
    (tmp_path / "violations.py").write_text(
        "amount = float(raw_amount)\nprice = float(raw_price)\nvector = float(component)\n",
        encoding="utf-8",
    )

    assert guard.main(str(tmp_path)) == 1
    captured = capsys.readouterr().out  # type: ignore[attr-defined]
    lines = [line for line in captured.splitlines() if "monetary float" in line]
    # One violation per line, newline-separated (the old guard printed a
    # literal backslash-n); the non-monetary float is not flagged.
    assert len(lines) == 2


def test_monetary_guard_requires_a_reason_on_waivers(tmp_path: Path) -> None:
    guard = _load_guard()
    (tmp_path / "waivers.py").write_text(
        "amount = float(raw)  # monetary-float-ok: display formatting only\n"
        "price = float(raw)  # monetary-float-ok:\n",
        encoding="utf-8",
    )

    violations = [
        finding
        for idx, line in enumerate(
            (tmp_path / "waivers.py").read_text(encoding="utf-8").splitlines(), start=1
        )
        if (finding := guard._line_violation(line)) is not None
    ]
    assert violations == ["monetary float waiver has no reason"]
