from __future__ import annotations

import weakref
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def _dispose_engine(engine: Engine) -> None:
    dispose = getattr(engine, "dispose", None)
    if callable(dispose):
        dispose()


class SqlAlchemyRepositoryBase:
    _engine: Engine
    _session_factory: sessionmaker[Session]
    _dispose_finalizer: Any

    def _configure_sqlalchemy(self, database_url: str) -> None:
        self._engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, future=True)
        self._dispose_finalizer = weakref.finalize(self, _dispose_engine, self._engine)

    def close(self) -> None:
        finalizer = getattr(self, "_dispose_finalizer", None)
        if finalizer is not None and finalizer.alive:
            finalizer()
