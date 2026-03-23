from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentDescriptor,
    RetrievalIndexJobDescriptor,
    RetrievalIndexStatus,
    RetrievalJobStatus,
    RetrievalSearchHit,
    RetrievalSourceDescriptor,
    RetrievalSourceKind,
)
from app.db.models import (
    RetrievalChunkModel,
    RetrievalDocumentModel,
    RetrievalIndexJobModel,
    RetrievalSourceModel,
)
from app.retrieval.search_scoring import score_terms


class SqlAlchemyRetrievalRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._engine = create_engine(database_url, future=True)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, future=True)

    def list_sources(self) -> list[RetrievalSourceDescriptor]:
        with self._session_factory() as session:
            sources = session.scalars(
                select(RetrievalSourceModel).order_by(RetrievalSourceModel.source_id)
            ).all()
            return [self._to_source_descriptor(source) for source in sources]

    def list_source_ids(self) -> list[str]:
        return [source.source_id for source in self.list_sources()]

    def get_source(self, source_id: str) -> RetrievalSourceDescriptor | None:
        with self._session_factory() as session:
            source = session.get(RetrievalSourceModel, source_id)
            if source is None:
                return None
            return self._to_source_descriptor(source)

    def list_documents_for_source(self, source_id: str) -> list[RetrievalDocumentDescriptor]:
        with self._session_factory() as session:
            documents = session.scalars(
                select(RetrievalDocumentModel)
                .where(RetrievalDocumentModel.source_id == source_id)
                .order_by(RetrievalDocumentModel.document_id)
            ).all()
            return [self._to_document_descriptor(session, document) for document in documents]

    def get_document(self, document_id: str) -> RetrievalDocumentDescriptor | None:
        with self._session_factory() as session:
            document = session.get(RetrievalDocumentModel, document_id)
            if document is None:
                return None
            return self._to_document_descriptor(session, document)

    def list_chunks_for_document(self, document_id: str) -> list[RetrievalChunkDescriptor]:
        with self._session_factory() as session:
            chunks = session.scalars(
                select(RetrievalChunkModel)
                .where(RetrievalChunkModel.document_id == document_id)
                .order_by(RetrievalChunkModel.chunk_order)
            ).all()
            return [self._to_chunk_descriptor(chunk) for chunk in chunks]

    def search_indexed_chunks(
        self, *, query: str, source_ids: list[str], limit: int
    ) -> list[RetrievalSearchHit]:
        with self._session_factory() as session:
            statement = (
                select(RetrievalChunkModel, RetrievalDocumentModel, RetrievalSourceModel)
                .join(
                    RetrievalDocumentModel,
                    RetrievalDocumentModel.document_id == RetrievalChunkModel.document_id,
                )
                .join(
                    RetrievalSourceModel,
                    RetrievalSourceModel.source_id == RetrievalChunkModel.source_id,
                )
                .where(RetrievalSourceModel.enabled.is_(True))
                .where(RetrievalDocumentModel.index_status == RetrievalIndexStatus.INDEXED.value)
                .where(RetrievalChunkModel.index_status == RetrievalIndexStatus.INDEXED.value)
            )
            if source_ids:
                statement = statement.where(RetrievalChunkModel.source_id.in_(source_ids))

            rows = session.execute(statement).all()
            ranked_hits: list[RetrievalSearchHit] = []
            for chunk, document, _source in rows:
                score = score_terms(
                    query=query,
                    searchable_text=f"{document.title} {chunk.preview}",
                )
                if score <= 0.0:
                    continue
                ranked_hits.append(
                    RetrievalSearchHit(
                        source_id=chunk.source_id,
                        document_id=chunk.document_id,
                        chunk_id=chunk.chunk_id,
                        score=score,
                        snippet=chunk.preview,
                    )
                )

            ranked_hits.sort(
                key=lambda hit: (-hit.score, hit.source_id, hit.document_id, hit.chunk_id)
            )
            return ranked_hits[:limit]

    def list_index_jobs(self) -> list[RetrievalIndexJobDescriptor]:
        with self._session_factory() as session:
            jobs = session.scalars(
                select(RetrievalIndexJobModel).order_by(RetrievalIndexJobModel.job_id)
            ).all()
            return [self._to_job_descriptor(session, job) for job in jobs]

    def get_index_job(self, job_id: str) -> RetrievalIndexJobDescriptor | None:
        with self._session_factory() as session:
            job = session.get(RetrievalIndexJobModel, job_id)
            if job is None:
                return None
            return self._to_job_descriptor(session, job)

    def save_index_job(self, descriptor: RetrievalIndexJobDescriptor) -> None:
        model = RetrievalIndexJobModel(
            job_id=descriptor.job_id,
            source_id=descriptor.source_id,
            status=descriptor.status.value,
            message=descriptor.message,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def set_source_index_status(self, *, source_id: str, index_status: str) -> None:
        with self._session_factory() as session:
            documents = session.scalars(
                select(RetrievalDocumentModel).where(RetrievalDocumentModel.source_id == source_id)
            ).all()
            for document in documents:
                document.index_status = index_status
            chunks = session.scalars(
                select(RetrievalChunkModel).where(RetrievalChunkModel.source_id == source_id)
            ).all()
            for chunk in chunks:
                chunk.index_status = index_status
            session.commit()

    def _to_source_descriptor(self, model: RetrievalSourceModel) -> RetrievalSourceDescriptor:
        return RetrievalSourceDescriptor(
            source_id=model.source_id,
            kind=RetrievalSourceKind(model.kind),
            enabled=model.enabled,
            description=model.description,
        )

    def _to_document_descriptor(
        self, session: Session, model: RetrievalDocumentModel
    ) -> RetrievalDocumentDescriptor:
        chunk_count = len(
            session.scalars(
                select(RetrievalChunkModel.chunk_id).where(
                    RetrievalChunkModel.document_id == model.document_id
                )
            ).all()
        )
        return RetrievalDocumentDescriptor(
            document_id=model.document_id,
            source_id=model.source_id,
            title=model.title,
            location=model.location,
            chunk_count=chunk_count,
            index_status=RetrievalIndexStatus(model.index_status),
        )

    def _to_chunk_descriptor(self, model: RetrievalChunkModel) -> RetrievalChunkDescriptor:
        return RetrievalChunkDescriptor(
            chunk_id=model.chunk_id,
            document_id=model.document_id,
            source_id=model.source_id,
            chunk_order=model.chunk_order,
            token_estimate=model.token_estimate,
            preview=model.preview,
            index_status=RetrievalIndexStatus(model.index_status),
        )

    def _to_job_descriptor(
        self, session: Session, model: RetrievalIndexJobModel
    ) -> RetrievalIndexJobDescriptor:
        document_count = len(
            session.scalars(
                select(RetrievalDocumentModel.document_id).where(
                    RetrievalDocumentModel.source_id == model.source_id
                )
            ).all()
        )
        chunk_count = len(
            session.scalars(
                select(RetrievalChunkModel.chunk_id).where(
                    RetrievalChunkModel.source_id == model.source_id
                )
            ).all()
        )
        return RetrievalIndexJobDescriptor(
            job_id=model.job_id,
            source_id=model.source_id,
            status=RetrievalJobStatus(model.status),
            document_count=document_count,
            chunk_count=chunk_count,
            message=model.message,
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
