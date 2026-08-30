from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.contracts.rate_cards import RateCard, RateCardScopeKind
from app.db.models import RateCardModel
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase


class SqlAlchemyRateCardRepository(SqlAlchemyRepositoryBase):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

    def list_cards(self) -> list[RateCard]:
        with self._session_factory() as session:
            models = session.scalars(select(RateCardModel).order_by(RateCardModel.card_id)).all()
            return [self._to_card(model) for model in models]

    def get_card(self, card_id: str) -> RateCard | None:
        with self._session_factory() as session:
            model = session.get(RateCardModel, card_id)
            if model is None:
                return None
            return self._to_card(model)

    def upsert_card(self, card: RateCard) -> None:
        with self._session_factory() as session:
            model = session.get(RateCardModel, card.card_id)
            if model is None:
                model = RateCardModel(card_id=card.card_id)
                session.add(model)
            model.scope_kind = card.scope_kind.value
            model.currency = card.currency
            model.input_cost_per_1k_tokens = card.input_cost_per_1k_tokens
            model.output_cost_per_1k_tokens = card.output_cost_per_1k_tokens
            model.effective_from_utc = card.effective_from_utc
            model.effective_to_utc = card.effective_to_utc
            model.created_at = card.created_at
            model.last_updated_at = card.last_updated_at
            session.commit()

    def _to_card(self, model: RateCardModel) -> RateCard:
        return RateCard(
            card_id=model.card_id,
            scope_kind=RateCardScopeKind(model.scope_kind),
            currency=model.currency,
            input_cost_per_1k_tokens=model.input_cost_per_1k_tokens,
            output_cost_per_1k_tokens=model.output_cost_per_1k_tokens,
            effective_from_utc=model.effective_from_utc,
            effective_to_utc=model.effective_to_utc,
            created_at=model.created_at,
            last_updated_at=model.last_updated_at,
        )

    def _ensure_sqlite_parent_directory(self) -> None:
        prefix = "sqlite:///"
        if not self._database_url.startswith(prefix):
            return
        db_path = self._database_url.removeprefix(prefix)
        if db_path == ":memory:":
            return
        path = Path(db_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
