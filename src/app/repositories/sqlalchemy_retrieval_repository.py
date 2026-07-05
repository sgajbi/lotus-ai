from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Callable

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.contracts.retrieval import (
    RetrievalChunkDescriptor,
    RetrievalDocumentDescriptor,
    RetrievalDocumentVersionDescriptor,
    RetrievalDocumentVersionLifecycleStatus,
    RetrievalIngestionAction,
    RetrievalIngestionJobDescriptor,
    RetrievalIngestionJobStatus,
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
    RetrievalDocumentVersionModel,
    RetrievalIngestionJobModel,
    RetrievalIndexJobModel,
    RetrievalSourceModel,
)
from app.repositories.sqlalchemy_repository_base import SqlAlchemyRepositoryBase
from app.retrieval.search_eligibility import is_live_search_chunk_eligible
from app.retrieval.search_hits import build_retrieval_search_hit
from app.retrieval.search_scoring import score_terms, tokenize


SEARCH_CANDIDATE_WINDOW_MIN = 50
SEARCH_CANDIDATE_WINDOW_MULTIPLIER = 20
SEARCH_CANDIDATE_WINDOW_MAX = 200


class SqlAlchemyRetrievalRepository(SqlAlchemyRepositoryBase):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._ensure_sqlite_parent_directory()
        self._configure_sqlalchemy(database_url)

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

    def list_document_versions(self) -> list[RetrievalDocumentVersionDescriptor]:
        with self._session_factory() as session:
            versions = session.scalars(
                select(RetrievalDocumentVersionModel).order_by(
                    RetrievalDocumentVersionModel.created_at.desc(),
                    RetrievalDocumentVersionModel.version_id.desc(),
                )
            ).all()
            return [self._to_document_version_descriptor(version) for version in versions]

    def save_document_version(self, descriptor: RetrievalDocumentVersionDescriptor) -> None:
        model = RetrievalDocumentVersionModel(
            version_id=descriptor.version_id,
            document_id=descriptor.document_id,
            source_id=descriptor.source_id,
            lifecycle_status=descriptor.lifecycle_status.value,
            refresh_action=descriptor.refresh_action.value,
            lineage_parent_version_id=descriptor.lineage_parent_version_id,
            title=descriptor.title,
            location=descriptor.location,
            created_at=descriptor.created_at,
            created_by=descriptor.created_by,
            notes=descriptor.notes,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def list_ingestion_jobs(self) -> list[RetrievalIngestionJobDescriptor]:
        with self._session_factory() as session:
            jobs = session.scalars(
                select(RetrievalIngestionJobModel).order_by(
                    RetrievalIngestionJobModel.requested_at.desc(),
                    RetrievalIngestionJobModel.job_id.desc(),
                )
            ).all()
            return [self._to_ingestion_job_descriptor(job) for job in jobs]

    def get_ingestion_job(self, job_id: str) -> RetrievalIngestionJobDescriptor | None:
        with self._session_factory() as session:
            job = session.get(RetrievalIngestionJobModel, job_id)
            if job is None:
                return None
            return self._to_ingestion_job_descriptor(job)

    def save_ingestion_job(self, descriptor: RetrievalIngestionJobDescriptor) -> None:
        model = RetrievalIngestionJobModel(
            job_id=descriptor.job_id,
            source_id=descriptor.source_id,
            document_id=descriptor.document_id,
            target_version_id=descriptor.target_version_id,
            requested_action=descriptor.requested_action.value,
            status=descriptor.status.value,
            requested_by=descriptor.requested_by,
            requested_at=descriptor.requested_at,
            message=descriptor.message,
        )
        with self._session_factory() as session:
            session.merge(model)
            session.commit()

    def search_indexed_chunks(
        self, *, query: str, source_ids: list[str], limit: int
    ) -> list[RetrievalSearchHit]:
        query_terms = sorted(tokenize(query))
        if not query_terms:
            return []
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

            term_filters = [
                or_(
                    func.lower(RetrievalDocumentModel.title).like(f"%{term}%"),
                    func.lower(RetrievalChunkModel.preview).like(f"%{term}%"),
                )
                for term in query_terms
            ]
            statement = (
                statement.where(or_(*term_filters))
                .order_by(
                    RetrievalChunkModel.source_id,
                    RetrievalChunkModel.document_id,
                    RetrievalChunkModel.chunk_order,
                    RetrievalChunkModel.chunk_id,
                )
                .limit(_search_candidate_window(limit))
            )
            rows = session.execute(statement).all()
            document_ids = {document.document_id for _chunk, document, _source in rows}
            source_ids_in_rows = {source.source_id for _chunk, _document, source in rows}
            versions_by_document_id = _load_document_versions_by_document_id(
                session=session,
                document_ids=document_ids,
                to_descriptor=self._to_document_version_descriptor,
            )
            ingestion_jobs_by_document_id = _load_ingestion_jobs_by_document_id(
                session=session,
                document_ids=document_ids,
                source_ids=source_ids_in_rows,
                to_descriptor=self._to_ingestion_job_descriptor,
            )
            ranked_hits: list[RetrievalSearchHit] = []
            for chunk, document, _source in rows:
                source_descriptor = self._to_source_descriptor(_source)
                document_descriptor = RetrievalDocumentDescriptor(
                    document_id=document.document_id,
                    source_id=document.source_id,
                    title=document.title,
                    location=document.location,
                    chunk_count=0,
                    index_status=RetrievalIndexStatus(document.index_status),
                )
                chunk_descriptor = self._to_chunk_descriptor(chunk)
                document_versions = versions_by_document_id[document.document_id]
                ingestion_jobs = ingestion_jobs_by_document_id[document.document_id]
                if not is_live_search_chunk_eligible(
                    source=source_descriptor,
                    document=document_descriptor,
                    chunk=chunk_descriptor,
                    document_versions=document_versions,
                    ingestion_jobs=ingestion_jobs,
                ):
                    continue
                score = score_terms(
                    query=query,
                    searchable_text=f"{document.title} {chunk.preview}",
                )
                if score <= 0.0:
                    continue
                ranked_hits.append(
                    build_retrieval_search_hit(
                        source=source_descriptor,
                        document=document_descriptor,
                        chunk=chunk_descriptor,
                        document_versions=document_versions,
                        score=score,
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

    def _to_document_version_descriptor(
        self, model: RetrievalDocumentVersionModel
    ) -> RetrievalDocumentVersionDescriptor:
        return RetrievalDocumentVersionDescriptor(
            version_id=model.version_id,
            document_id=model.document_id,
            source_id=model.source_id,
            title=model.title,
            location=model.location,
            lifecycle_status=RetrievalDocumentVersionLifecycleStatus(model.lifecycle_status),
            refresh_action=RetrievalIngestionAction(model.refresh_action),
            lineage_parent_version_id=model.lineage_parent_version_id,
            created_at=model.created_at,
            created_by=model.created_by,
            notes=model.notes,
        )

    def _to_ingestion_job_descriptor(
        self, model: RetrievalIngestionJobModel
    ) -> RetrievalIngestionJobDescriptor:
        return RetrievalIngestionJobDescriptor(
            job_id=model.job_id,
            source_id=model.source_id,
            document_id=model.document_id,
            target_version_id=model.target_version_id,
            requested_action=RetrievalIngestionAction(model.requested_action),
            status=RetrievalIngestionJobStatus(model.status),
            requested_by=model.requested_by,
            requested_at=model.requested_at,
            message=model.message,
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


def _search_candidate_window(limit: int) -> int:
    return min(
        max(limit * SEARCH_CANDIDATE_WINDOW_MULTIPLIER, SEARCH_CANDIDATE_WINDOW_MIN),
        SEARCH_CANDIDATE_WINDOW_MAX,
    )


def _load_document_versions_by_document_id(
    *,
    session: Session,
    document_ids: set[str],
    to_descriptor: Callable[[RetrievalDocumentVersionModel], RetrievalDocumentVersionDescriptor],
) -> dict[str, list[RetrievalDocumentVersionDescriptor]]:
    versions_by_document_id: dict[str, list[RetrievalDocumentVersionDescriptor]] = defaultdict(list)
    if not document_ids:
        return versions_by_document_id
    versions = session.scalars(
        select(RetrievalDocumentVersionModel).where(
            RetrievalDocumentVersionModel.document_id.in_(document_ids)
        )
    ).all()
    for version in versions:
        versions_by_document_id[version.document_id].append(to_descriptor(version))
    return versions_by_document_id


def _load_ingestion_jobs_by_document_id(
    *,
    session: Session,
    document_ids: set[str],
    source_ids: set[str],
    to_descriptor: Callable[[RetrievalIngestionJobModel], RetrievalIngestionJobDescriptor],
) -> dict[str, list[RetrievalIngestionJobDescriptor]]:
    jobs_by_document_id: dict[str, list[RetrievalIngestionJobDescriptor]] = defaultdict(list)
    if not document_ids:
        return jobs_by_document_id
    jobs = session.scalars(
        select(RetrievalIngestionJobModel).where(
            or_(
                RetrievalIngestionJobModel.document_id.in_(document_ids),
                and_(
                    RetrievalIngestionJobModel.source_id.in_(source_ids),
                    RetrievalIngestionJobModel.document_id.is_(None),
                ),
            )
        )
    ).all()
    for job in jobs:
        descriptor = to_descriptor(job)
        if job.document_id is not None:
            jobs_by_document_id[job.document_id].append(descriptor)
            continue
        for document_id in document_ids:
            jobs_by_document_id[document_id].append(descriptor)
    return jobs_by_document_id
