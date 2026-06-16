from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    DDL,
    ForeignKey,
    Float,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    cast,
    event,
    func,
    literal_column,
    text as sql_text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from sqlalchemy.types import UserDefinedType


class Ltree(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **kw: Any) -> str:
        return "LTREE"

    def bind_expression(self, bindvalue: Any) -> Any:
        return cast(bindvalue, self)


class Base(DeclarativeBase):
    pass


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    repo_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pull_requests: Mapped[list[PullRequest]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    file_paths: Mapped[list[FilePath]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    login_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    comments: Mapped[list[ChangeComment]] = relationship(
        back_populates="author",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("idx_auth_sessions_token", "session_token"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    session_token: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class PullRequest(Base):
    __tablename__ = "pull_requests"
    __table_args__ = (
        UniqueConstraint("repository_id", "number"),
        Index("idx_pull_requests_repo_state", "repository_id", "state"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    pr_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    repo_key: Mapped[str] = mapped_column(Text, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    base_ref: Mapped[str] = mapped_column(Text, nullable=False)
    head_ref: Mapped[str] = mapped_column(Text, nullable=False)
    base_sha: Mapped[str | None] = mapped_column(Text)
    head_sha: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    labels: Mapped[list[str]] = mapped_column(
        ARRAY(Text()),
        default=list,
        server_default=sql_text("'{}'::text[]"),
        nullable=False,
    )
    raw_graphql: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    repository: Mapped[Repository] = relationship(back_populates="pull_requests")
    files: Mapped[list[PullRequestFile]] = relationship(
        back_populates="pull_request",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class FilePath(Base):
    __tablename__ = "file_paths"
    __table_args__ = (
        UniqueConstraint("repository_id", "path"),
        Index("idx_file_paths_path_tree", "path_tree", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    path_tree: Mapped[str] = mapped_column(Ltree(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    repository: Mapped[Repository] = relationship(back_populates="file_paths")
    pull_request_files: Mapped[list[PullRequestFile]] = relationship(
        back_populates="file_path",
        passive_deletes=True,
    )


class PullRequestFile(Base):
    __tablename__ = "pr_files"
    __table_args__ = (
        UniqueConstraint("pull_request_id", "path"),
        Index("idx_pr_files_path_tree", "path_tree", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    pr_file_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    pull_request_id: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False
    )
    file_path_id: Mapped[int] = mapped_column(
        ForeignKey("file_paths.id", ondelete="CASCADE"), nullable=False
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    path_tree: Mapped[str] = mapped_column(Ltree(), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    additions: Mapped[int] = mapped_column(Integer, nullable=False)
    deletions: Mapped[int] = mapped_column(Integer, nullable=False)
    changes: Mapped[int] = mapped_column(Integer, nullable=False)
    patch: Mapped[str | None] = mapped_column(Text)
    raw_rest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    stored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pull_request: Mapped[PullRequest] = relationship(back_populates="files")
    file_path: Mapped[FilePath] = relationship(back_populates="pull_request_files")
    hunks: Mapped[list[PullRequestHunk]] = relationship(
        back_populates="pull_request_file",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ChangeComment(Base):
    __tablename__ = "change_comments"
    __table_args__ = (
        Index("idx_change_comments_pr_file", "pull_request_id", "file_path_id"),
        Index("idx_change_comments_author", "author_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    pull_request_id: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False
    )
    file_path_id: Mapped[int] = mapped_column(
        ForeignKey("file_paths.id", ondelete="CASCADE"), nullable=False
    )
    author_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pull_request: Mapped[PullRequest] = relationship()
    file_path: Mapped[FilePath] = relationship()
    author: Mapped[User] = relationship(back_populates="comments")


class PullRequestHunk(Base):
    __tablename__ = "pr_file_hunks"
    __table_args__ = (UniqueConstraint("pr_file_id", "hunk_index"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    hunk_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    pr_file_id: Mapped[int] = mapped_column(
        ForeignKey("pr_files.id", ondelete="CASCADE"), nullable=False
    )
    hunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    old_start: Mapped[int] = mapped_column(Integer, nullable=False)
    old_lines: Mapped[int] = mapped_column(Integer, nullable=False)
    new_start: Mapped[int] = mapped_column(Integer, nullable=False)
    new_lines: Mapped[int] = mapped_column(Integer, nullable=False)
    header: Mapped[str] = mapped_column(Text, nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False)
    hunk_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    pull_request_file: Mapped[PullRequestFile] = relationship(back_populates="hunks")


Index(
    "idx_pr_file_hunks_new_range",
    func.int4range(
        PullRequestHunk.new_start,
        PullRequestHunk.new_start + PullRequestHunk.new_lines,
        literal_column("'[]'"),
    ),
    postgresql_using="gist",
)


class RawPayload(Base):
    __tablename__ = "raw_payloads"
    __table_args__ = (UniqueConstraint("entity_type", "entity_key", "source"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_key: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StaticAnalysisSnapshot(Base):
    __tablename__ = "static_analysis_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "repository_id",
            "commit_sha",
            "codeql_database_uri",
            "query_pack_version",
            name="uq_static_analysis_snapshot_identity",
        ),
        Index(
            "idx_static_analysis_snapshots_repo_commit",
            "repository_id",
            "commit_sha",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    commit_sha: Mapped[str] = mapped_column(Text, nullable=False)
    codeql_database_uri: Mapped[str] = mapped_column(Text, nullable=False)
    query_pack_version: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PullRequestCodeqlChange(Base):
    __tablename__ = "pr_codeql_changes"
    __table_args__ = (
        Index("idx_pr_codeql_changes_pr", "pull_request_id"),
        Index("idx_pr_codeql_changes_snapshot", "snapshot_id"),
        Index("idx_pr_codeql_changes_symbol", "symbol_key"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    pull_request_id: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False
    )
    file_path_id: Mapped[int] = mapped_column(
        ForeignKey("file_paths.id", ondelete="CASCADE"), nullable=False
    )
    hunk_id: Mapped[int | None] = mapped_column(
        ForeignKey("pr_file_hunks.id", ondelete="SET NULL")
    )
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("static_analysis_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    symbol_key: Mapped[str] = mapped_column(Text, nullable=False)
    symbol_name: Mapped[str] = mapped_column(Text, nullable=False)
    symbol_kind: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StaticImpactFinding(Base):
    __tablename__ = "static_impact_findings"
    __table_args__ = (
        Index("idx_static_impact_findings_repo", "repository_id"),
        Index("idx_static_impact_findings_pr", "pull_request_id"),
        Index("idx_static_impact_findings_file", "file_path_id"),
        Index("idx_static_impact_findings_snapshot", "snapshot_id"),
        Index("idx_static_impact_findings_type", "finding_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False
    )
    pull_request_id: Mapped[int] = mapped_column(
        ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False
    )
    file_path_id: Mapped[int] = mapped_column(
        ForeignKey("file_paths.id", ondelete="CASCADE"), nullable=False
    )
    snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("static_analysis_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    finding_type: Mapped[str] = mapped_column(Text, nullable=False)
    start_symbol_key: Mapped[str | None] = mapped_column(Text)
    end_symbol_key: Mapped[str | None] = mapped_column(Text)
    impact_path: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    affected_paths: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    affected_roles: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    related_tests: Mapped[list[Any]] = mapped_column(
        JSONB,
        default=list,
        server_default=sql_text("'[]'::jsonb"),
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    query_id: Mapped[str] = mapped_column(Text, nullable=False)
    query_version: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        default=dict,
        server_default=sql_text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


event.listen(
    Base.metadata,
    "before_create",
    DDL("CREATE EXTENSION IF NOT EXISTS ltree").execute_if(dialect="postgresql"),
)


def ensure_schema(bind: Engine | Connection | Session) -> None:
    if isinstance(bind, Session):
        bind = bind.get_bind()
    Base.metadata.create_all(bind)
