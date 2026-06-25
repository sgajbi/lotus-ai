from __future__ import annotations

from pathlib import Path
import sys


def ensure_repo_src_first(*, script_file: str) -> Path:
    repo_root = Path(script_file).resolve().parents[1]
    src_root = repo_root / "src"
    src_root_text = str(src_root)
    sys.path = [path for path in sys.path if path != src_root_text]
    sys.path.insert(0, src_root_text)

    app_module = sys.modules.get("app")
    app_file = getattr(app_module, "__file__", "") if app_module is not None else ""
    if app_module is not None and not str(app_file).startswith(src_root_text):
        sys.modules.pop("app", None)

    return repo_root
