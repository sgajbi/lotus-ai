from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import Select, create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentDescriptor,
    RetrievalDocumentPromotionStatus,
    RetrievalEmbeddingStatus,
    RetrievalExecutionRequest,
    RetrievalIndexedChunkDescriptor,
    RetrievalIndexJobEventDescriptor,
    RetrievalIndexJobEventStatus,
    RetrievalIndexJobDescriptor,
    RetrievalIndexJobRefreshDescriptor,
    RetrievalIndexJobRefreshStatus,
    RetrievalIndexStatus,
    RetrievalJobStatus,
    RetrievalPipelineStage,
    RetrievalSearchHit,
    RetrievalSourceDescriptor,
    RetrievalSourceKind,
)
from app.retrieval.foundation_embedding import build_preview_embedding, cosine_similarity
from app.retrieval.indexed_search_backend import build_indexed_hits
from app.retrieval.indexing_refresh import (
    build_indexed_chunk_refresh_record,
    build_refresh_descriptor,
    build_refresh_event,
)
from app.services.retrieval_text_scoring import lexical_overlap_ratio, tokenize_retrieval_text
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
        self._register_sqlite_functions()
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

    def list_searchable_indexed_chunks(
        self, source_ids: list[str]
    ) -> list[RetrievalIndexedChunkDescriptor]:
        with self._session_factory() as session:
            statement = self._indexed_chunk_query().order_by(
                RetrievalChunkEmbeddingModel.source_id,
                RetrievalChunkEmbeddingModel.document_id,
                RetrievalChunkModel.chunk_order,
            )
            if source_ids:
                statement = statement.where(RetrievalChunkEmbeddingModel.source_id.in_(source_ids))
            rows = session.execute(statement).all()
            return [
                RetrievalIndexedChunkDescriptor(
                    embedding_id=embedding.embedding_id,
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    source_id=chunk.source_id,
                    document_title=document.title,
                    content_checksum=chunk.content_checksum,
                    snippet=chunk.preview,
                    embedding_model=embedding.embedding_model,
                    embedding_status=RetrievalEmbeddingStatus(embedding.embedding_status),
                    vector_dimensions=embedding.vector_dimensions,
                    embedding_vector=embedding.embedding_vector,
                )
                for embedding, chunk, document in rows
            ]

    def has_searchable_indexed_chunks(self, source_ids: list[str]) -> bool:
        with self._session_factory() as session:
            statement = self._indexed_chunk_query()
            if source_ids:
                statement = statement.where(RetrievalChunkEmbeddingModel.source_id.in_(source_ids))
            return bool(session.execute(statement.limit(1)).first())

    def search_indexed_hits(
        self, request: RetrievalExecutionRequest
    ) -> list[RetrievalSearchHit]:
        if self._database_url.startswith("sqlite:///"):
            return self._search_indexed_hits_sqlite(request)
        return build_indexed_hits(
            indexed_chunks=self.list_searchable_indexed_chunks(request.source_ids),
            request=request,
        )

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

    def refresh_index_job(self, job_id: str) -> RetrievalIndexJobRefreshDescriptor | None:
        with self._session_factory() as session:
            job = session.get(RetrievalIndexJobModel, job_id)
            if job is None:
                return None

            documents = session.scalars(
                select(RetrievalDocumentModel)
                .where(
                    RetrievalDocumentModel.source_id == job.source_id,
                    RetrievalDocumentModel.promotion_status
                    == RetrievalDocumentPromotionStatus.SEARCHABLE.value,
                )
                .order_by(RetrievalDocumentModel.document_id)
            ).all()
            if not documents:
                message = (
                    "Deterministic indexing refresh is blocked because no searchable documents "
                    "exist for this source."
                )
                event = self._persist_refresh_event(
                    session=session,
                    job_id=job_id,
                    status=RetrievalIndexJobRefreshStatus.BLOCKED,
                    notes=message,
                )
                session.commit()
                return build_refresh_descriptor(
                    status=RetrievalIndexJobRefreshStatus.BLOCKED,
                    refreshed_document_count=0,
                    refreshed_chunk_count=0,
                    persisted_embedding_count=0,
                    replayed_embedding_count=0,
                    message=message,
                    event=event,
                )

            refreshed_chunk_count = 0
            persisted_embedding_count = 0
            replayed_embedding_count = 0
            for document_model in documents:
                document_model.index_status = RetrievalIndexStatus.INDEXED.value
                document_descriptor = self._to_document_descriptor(session, document_model)
                chunks = session.scalars(
                    select(RetrievalChunkModel)
                    .where(RetrievalChunkModel.document_id == document_model.document_id)
                    .order_by(RetrievalChunkModel.chunk_order)
                ).all()
                for chunk_model in chunks:
                    refreshed_chunk_count += 1
                    chunk_model.index_status = RetrievalIndexStatus.INDEXED.value
                    chunk_descriptor = self._to_chunk_descriptor(chunk_model)
                    refresh_record = build_indexed_chunk_refresh_record(
                        document=document_descriptor,
                        chunk=chunk_descriptor,
                    )
                    existing_embedding = session.get(
                        RetrievalChunkEmbeddingModel,
                        refresh_record.embedding_id,
                    )
                    if existing_embedding is None:
                        persisted_embedding_count += 1
                        session.add(
                            RetrievalChunkEmbeddingModel(
                                embedding_id=refresh_record.embedding_id,
                                chunk_id=chunk_model.chunk_id,
                                document_id=chunk_model.document_id,
                                source_id=chunk_model.source_id,
                                embedding_model=refresh_record.embedding_model,
                                embedding_status=RetrievalEmbeddingStatus.PERSISTED.value,
                                vector_dimensions=refresh_record.vector_dimensions,
                                embedding_vector=refresh_record.embedding_vector,
                                content_checksum=refresh_record.content_checksum,
                            )
                        )
                    else:
                        replayed_embedding_count += 1
                        existing_embedding.embedding_model = refresh_record.embedding_model
                        existing_embedding.embedding_status = RetrievalEmbeddingStatus.PERSISTED.value
                        existing_embedding.vector_dimensions = refresh_record.vector_dimensions
                        existing_embedding.embedding_vector = refresh_record.embedding_vector
                        existing_embedding.content_checksum = refresh_record.content_checksum
                    session.flush()

            job.status = RetrievalJobStatus.COMPLETED.value
            job.message = (
                "Promoted searchable documents were deterministically re-indexed for bounded retrieval."
            )
            event = self._persist_refresh_event(
                session=session,
                job_id=job_id,
                status=RetrievalIndexJobRefreshStatus.COMPLETED,
                notes=job.message,
            )
            session.commit()
            return build_refresh_descriptor(
                status=RetrievalIndexJobRefreshStatus.COMPLETED,
                refreshed_document_count=len(documents),
                refreshed_chunk_count=refreshed_chunk_count,
                persisted_embedding_count=persisted_embedding_count,
                replayed_embedding_count=replayed_embedding_count,
                message=job.message,
                event=event,
            )

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

    def _indexed_chunk_query(self) -> Select[tuple[RetrievalChunkEmbeddingModel, RetrievalChunkModel, RetrievalDocumentModel]]:
        return (
            select(
                RetrievalChunkEmbeddingModel,
                RetrievalChunkModel,
                RetrievalDocumentModel,
            )
            .join(RetrievalChunkModel, RetrievalChunkModel.chunk_id == RetrievalChunkEmbeddingModel.chunk_id)
            .join(
                RetrievalDocumentModel,
                RetrievalDocumentModel.document_id == RetrievalChunkEmbeddingModel.document_id,
            )
            .where(
                RetrievalDocumentModel.promotion_status
                == RetrievalDocumentPromotionStatus.SEARCHABLE.value,
                RetrievalDocumentModel.index_status == RetrievalIndexStatus.INDEXED.value,
                RetrievalChunkModel.index_status == RetrievalIndexStatus.INDEXED.value,
                RetrievalChunkEmbeddingModel.embedding_status
                == RetrievalEmbeddingStatus.PERSISTED.value,
                RetrievalChunkEmbeddingModel.content_checksum == RetrievalChunkModel.content_checksum,
            )
        )

    def _search_indexed_hits_sqlite(
        self, request: RetrievalExecutionRequest
    ) -> list[RetrievalSearchHit]:
        query_embedding_json = json.dumps(build_preview_embedding(request.query))
        query_terms_json = json.dumps(sorted(tokenize_retrieval_text(request.query)))
        with self._session_factory() as session:
            lexical_score = func.lotus_ai_lexical_score(
                query_terms_json,
                RetrievalDocumentModel.title,
                RetrievalChunkModel.preview,
            )
            vector_score = func.lotus_ai_vector_score(
                query_embedding_json,
                RetrievalChunkEmbeddingModel.embedding_vector,
            )
            combined_score = (vector_score * 0.75) + (lexical_score * 0.25)
            statement = (
                select(
                    RetrievalChunkEmbeddingModel.source_id,
                    RetrievalChunkEmbeddingModel.document_id,
                    RetrievalChunkEmbeddingModel.chunk_id,
                    RetrievalChunkModel.preview,
                    combined_score.label("score"),
                )
                .select_from(RetrievalChunkEmbeddingModel)
                .join(
                    RetrievalChunkModel,
                    RetrievalChunkModel.chunk_id == RetrievalChunkEmbeddingModel.chunk_id,
                )
                .join(
                    RetrievalDocumentModel,
                    RetrievalDocumentModel.document_id == RetrievalChunkEmbeddingModel.document_id,
                )
                .where(
                    RetrievalDocumentModel.promotion_status
                    == RetrievalDocumentPromotionStatus.SEARCHABLE.value,
                    RetrievalDocumentModel.index_status == RetrievalIndexStatus.INDEXED.value,
                    RetrievalChunkModel.index_status == RetrievalIndexStatus.INDEXED.value,
                    RetrievalChunkEmbeddingModel.embedding_status
                    == RetrievalEmbeddingStatus.PERSISTED.value,
                    RetrievalChunkEmbeddingModel.content_checksum
                    == RetrievalChunkModel.content_checksum,
                    lexical_score > 0.0,
                )
                .order_by(
                    combined_score.desc(),
                    RetrievalChunkEmbeddingModel.source_id,
                    RetrievalChunkEmbeddingModel.document_id,
                    RetrievalChunkEmbeddingModel.chunk_id,
                )
                .limit(request.limit)
            )
            if request.source_ids:
                statement = statement.where(
                    RetrievalChunkEmbeddingModel.source_id.in_(request.source_ids)
                )
            rows = session.execute(statement).all()
            return [
                RetrievalSearchHit(
                    source_id=source_id,
                    document_id=document_id,
                    chunk_id=chunk_id,
                    score=round(float(score), 6),
                    snippet=snippet,
                )
                for source_id, document_id, chunk_id, snippet, score in rows
            ]

    def _persist_refresh_event(
        self,
        *,
        session: Session,
        job_id: str,
        status: RetrievalIndexJobRefreshStatus,
        notes: str,
    ) -> RetrievalIndexJobEventDescriptor:
        ordinal = (
            self._count_rows(
                session,
                select(func.count())
                .select_from(RetrievalIndexJobEventModel)
                .where(RetrievalIndexJobEventModel.job_id == job_id),
            )
            + 1
        )
        descriptor = build_refresh_event(
            job_id=job_id,
            ordinal=ordinal,
            status=status,
            notes=notes,
        )
        session.add(
            RetrievalIndexJobEventModel(
                event_id=descriptor.event_id,
                job_id=descriptor.job_id,
                stage=descriptor.stage.value,
                status=descriptor.status.value,
                recorded_at=descriptor.recorded_at,
                notes=descriptor.notes,
            )
        )
        return descriptor

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

    def _register_sqlite_functions(self) -> None:
        if not self._database_url.startswith("sqlite:///"):
            return

        @event.listens_for(self._engine, "connect")
        def _register_functions(dbapi_connection: Any, _connection_record: Any) -> None:
            dbapi_connection.create_function(
                "lotus_ai_vector_score",
                2,
                self._sqlite_vector_score,
            )
            dbapi_connection.create_function(
                "lotus_ai_lexical_score",
                3,
                self._sqlite_lexical_score,
            )

    def _sqlite_vector_score(self, query_embedding_json: str, embedding_vector_json: str) -> float:
        try:
            query_embedding = json.loads(query_embedding_json)
            embedding_vector = json.loads(embedding_vector_json)
        except (TypeError, json.JSONDecodeError):
            return 0.0
        if not isinstance(query_embedding, list) or not isinstance(embedding_vector, list):
            return 0.0
        return cosine_similarity(
            [float(value) for value in query_embedding],
            [float(value) for value in embedding_vector],
        )

    def _sqlite_lexical_score(self, query_terms_json: str, title: str, preview: str) -> float:
        try:
            query_terms = json.loads(query_terms_json)
        except (TypeError, json.JSONDecodeError):
            return 0.0
        if not isinstance(query_terms, list):
            return 0.0
        return lexical_overlap_ratio(
            query_terms={str(term) for term in query_terms},
            searchable_text=f"{title} {preview}",
        )
