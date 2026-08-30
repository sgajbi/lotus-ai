"""Rate-card catalogue, seed parity, and effective dating (issue #178, slice 1)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import settings
from app.contracts.rate_cards import RateCardScopeKind
from app.services.provider_usage_accounting import (
    DEFAULT_LIVE_TEXT_CARD_ID,
    ensure_rate_cards_seeded,
    estimate_live_text_cost_usd,
    resolve_effective_live_text_card,
)
from app.services.rate_card_store import (
    get_rate_card_repository,
    reset_rate_card_store_cache,
)

SRC_ROOT = Path(__file__).resolve().parents[2] / "src" / "app"


@pytest.fixture(autouse=True)
def _fresh_store() -> Iterator[None]:
    reset_rate_card_store_cache()
    yield
    reset_rate_card_store_cache()


@pytest.fixture
def _legacy_scalars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "live_text_input_cost_per_1k_tokens", 0.01)
    monkeypatch.setattr(settings, "live_text_output_cost_per_1k_tokens", 0.03)


def test_seed_migrates_the_scalars_and_estimation_is_cutover_identical(
    _legacy_scalars: None,
) -> None:
    # The exact arithmetic the scalars produced, now sourced from the card.
    assert estimate_live_text_cost_usd(input_tokens=1000, output_tokens=1000) == 0.04
    assert estimate_live_text_cost_usd(input_tokens=500, output_tokens=100) == round(
        0.5 * 0.01 + 0.1 * 0.03, 8
    )

    card = get_rate_card_repository().get_card(DEFAULT_LIVE_TEXT_CARD_ID)
    assert card is not None
    assert card.scope_kind is RateCardScopeKind.DEFAULT_LIVE_TEXT
    assert card.input_cost_per_1k_tokens == 0.01
    assert card.output_cost_per_1k_tokens == 0.03


def test_no_scalars_means_no_card_and_no_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "live_text_input_cost_per_1k_tokens", None)
    monkeypatch.setattr(settings, "live_text_output_cost_per_1k_tokens", None)

    assert estimate_live_text_cost_usd(input_tokens=10, output_tokens=10) is None
    assert get_rate_card_repository().list_cards() == []
    assert estimate_live_text_cost_usd(input_tokens=None, output_tokens=10) is None


def test_seed_is_idempotent_and_follows_scalar_changes(
    monkeypatch: pytest.MonkeyPatch, _legacy_scalars: None
) -> None:
    ensure_rate_cards_seeded()
    first = get_rate_card_repository().get_card(DEFAULT_LIVE_TEXT_CARD_ID)
    assert first is not None

    ensure_rate_cards_seeded()
    second = get_rate_card_repository().get_card(DEFAULT_LIVE_TEXT_CARD_ID)
    assert second == first

    monkeypatch.setattr(settings, "live_text_output_cost_per_1k_tokens", 0.05)
    ensure_rate_cards_seeded()
    updated = get_rate_card_repository().get_card(DEFAULT_LIVE_TEXT_CARD_ID)
    assert updated is not None
    assert updated.output_cost_per_1k_tokens == 0.05
    assert updated.created_at == first.created_at


def test_effective_dating_bounds_the_card(_legacy_scalars: None) -> None:
    ensure_rate_cards_seeded()
    repository = get_rate_card_repository()
    card = repository.get_card(DEFAULT_LIVE_TEXT_CARD_ID)
    assert card is not None

    repository.upsert_card(card.model_copy(update={"effective_to_utc": "2026-01-01T00:00:00Z"}))
    assert resolve_effective_live_text_card(at_utc="2026-06-01T00:00:00Z") is None
    assert resolve_effective_live_text_card(at_utc="2025-06-01T00:00:00Z") is not None

    repository.upsert_card(
        card.model_copy(
            update={
                "effective_from_utc": "2026-09-01T00:00:00Z",
                "effective_to_utc": None,
            }
        )
    )
    assert resolve_effective_live_text_card(at_utc="2026-08-30T00:00:00Z") is None
    assert resolve_effective_live_text_card(at_utc="2026-09-02T00:00:00Z") is not None


def test_store_accessor_fails_closed_on_bad_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rate_card_store_mode", "sqlalchemy")
    monkeypatch.setattr(settings, "database_url", None)
    with pytest.raises(RuntimeError, match="LOTUS_AI_DATABASE_URL is required"):
        get_rate_card_repository()
    monkeypatch.setattr(settings, "rate_card_store_mode", "abacus")
    with pytest.raises(RuntimeError, match="Unsupported LOTUS_AI_RATE_CARD_STORE_MODE"):
        get_rate_card_repository()


def test_sqlalchemy_round_trip_and_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, _legacy_scalars: None
) -> None:
    from tests.support.migration_runner import upgrade_database_to_head

    database_url = f"sqlite:///{tmp_path / 'rate-cards.db'}"
    upgrade_database_to_head(database_url)
    monkeypatch.setattr(settings, "rate_card_store_mode", "sqlalchemy")
    monkeypatch.setattr(settings, "database_url", database_url)

    assert estimate_live_text_cost_usd(input_tokens=1000, output_tokens=0) == 0.01

    # Restart: truth must come back from SQL with provenance intact.
    seeded = get_rate_card_repository().get_card(DEFAULT_LIVE_TEXT_CARD_ID)
    assert seeded is not None
    reset_rate_card_store_cache()
    reloaded = get_rate_card_repository().get_card(DEFAULT_LIVE_TEXT_CARD_ID)
    assert reloaded == seeded


def test_sqlalchemy_repository_prepares_each_sqlite_location_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.repositories.sqlalchemy_rate_card_repository import SqlAlchemyRateCardRepository

    SqlAlchemyRateCardRepository("sqlite:///:memory:").close()
    monkeypatch.chdir(tmp_path)
    SqlAlchemyRateCardRepository("sqlite:///data/nested/cards.db").close()
    assert (tmp_path / "data" / "nested").is_dir()
    SqlAlchemyRateCardRepository("postgresql+psycopg://user:secret@localhost:5432/db").close()


def test_cost_scalars_are_read_only_by_config_and_the_seed() -> None:
    """#178's single-source guard: the legacy scalars are seed inputs. A new
    runtime reader must show up here (eval_runtime_execution still WRITES them
    - the mutation #148 owns - and is listed until that issue lands)."""

    pattern = re.compile(r"live_text_(?:input|output)_cost_per_1k_tokens")
    referencing = {
        path.relative_to(SRC_ROOT).as_posix()
        for path in SRC_ROOT.rglob("*.py")
        if pattern.search(path.read_text(encoding="utf-8"))
    }
    assert referencing == {
        "config.py",
        "services/provider_usage_accounting.py",
        "services/eval_runtime_execution.py",
    }
