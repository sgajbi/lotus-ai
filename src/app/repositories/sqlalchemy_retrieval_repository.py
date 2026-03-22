from __future__ import annotations

from pathlib import Path

from sqlalchemy import Select, create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentDescriptor,
    RetrievalDocumentPromotionStatus,
    RetrievalIndexJobEventDescriptor,
    RetrievalIndexJobEventStatus,
    RetrievalIndexJobDescriptor,
    RetrievalIndexStatus,
    RetrievalJobStatus,
    RetrievalPipelineStage,
    RetrievalSourceDescriptor,
    RetrievalSourceKind,
)
from app.db.models import (
    RetrievalChunkModel,
    RetrievalChunkEmbeddingModel,
    RetrievalDocumentModel,
    RetrievalIndexJobEventModel,
    RetrievalIndexJobModel,
    RetrievalSourceModel,
)


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

    def count_embedding_records(self) -> int:
        with self._session_factory() as session:
            return self._count_rows(
                session, select(func.count()).select_from(RetrievalChunkEmbeddingModel)
            )

    def count_embedding_records_for_source(self, source_id: str) -> int:
        with self._session_factory() as session:
            return self._count_rows(
                session,
                select(func.count())
                .select_from(RetrievalChunkEmbeddingModel)
                .where(RetrievalChunkEmbeddingModel.source_id == source_id),
            )

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

    def list_index_job_events(self, job_id: str) -> list[RetrievalIndexJobEventDescriptor]:
        with self._session_factory() as session:
            events = session.scalars(
                select(RetrievalIndexJobEventModel)
                .where(RetrievalIndexJobEventModel.job_id == job_id)
                .order_by(
                    RetrievalIndexJobEventModel.recorded_at,
                    RetrievalIndexJobEventModel.event_id,
                )
            ).all()
            return [self._to_job_event_descriptor(event) for event in events]

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
        chunk_count = self._count_rows(
            session,
            select(func.count())
            .select_from(RetrievalChunkModel)
            .where(RetrievalChunkModel.document_id == model.document_id),
        )
        return RetrievalDocumentDescriptor(
            document_id=model.document_id,
            source_id=model.source_id,
            title=model.title,
            location=model.location,
            promotion_status=RetrievalDocumentPromotionStatus(model.promotion_status),
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
            content_checksum=model.content_checksum,
            preview=model.preview,
            index_status=RetrievalIndexStatus(model.index_status),
        )

    def _to_job_descriptor(
        self, session: Session, model: RetrievalIndexJobModel
    ) -> RetrievalIndexJobDescriptor:
        document_count = self._count_rows(
            session,
            select(func.count())
            .select_from(RetrievalDocumentModel)
            .where(RetrievalDocumentModel.source_id == model.source_id),
        )
        chunk_count = self._count_rows(
            session,
            select(func.count())
            .select_from(RetrievalChunkModel)
            .where(RetrievalChunkModel.source_id == model.source_id),
        )
        return RetrievalIndexJobDescriptor(
            job_id=model.job_id,
            source_id=model.source_id,
            status=RetrievalJobStatus(model.status),
            document_count=document_count,
            chunk_count=chunk_count,
            embedding_record_count=self._count_rows(
                session,
                select(func.count())
                .select_from(RetrievalChunkEmbeddingModel)
                .where(RetrievalChunkEmbeddingModel.source_id == model.source_id),
            ),
            message=model.message,
        )

    def _to_job_event_descriptor(
        self, model: RetrievalIndexJobEventModel
    ) -> RetrievalIndexJobEventDescriptor:
        return RetrievalIndexJobEventDescriptor(
            event_id=model.event_id,
            job_id=model.job_id,
            stage=RetrievalPipelineStage(model.stage),
            status=RetrievalIndexJobEventStatus(model.status),
            recorded_at=model.recorded_at,
            notes=model.notes,
        )

    def _count_rows(self, session: Session, statement: Select[tuple[int]]) -> int:
        return int(session.scalar(statement) or 0)

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
