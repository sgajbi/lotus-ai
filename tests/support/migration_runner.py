from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config


REPO_ROOT = Path(__file__).resolve().parents[2]


def upgrade_database_to_head(database_url: str) -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    previous_lotus_ai_database_url = os.environ.get("LOTUS_AI_DATABASE_URL")
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["LOTUS_AI_DATABASE_URL"] = database_url
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(config, "head")
    finally:
        if previous_lotus_ai_database_url is None:
            os.environ.pop("LOTUS_AI_DATABASE_URL", None)
        else:
            os.environ["LOTUS_AI_DATABASE_URL"] = previous_lotus_ai_database_url
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
