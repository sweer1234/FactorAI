from contextlib import contextmanager

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from .config import settings


engine = create_engine(f"sqlite:///{settings.sqlite_path}", connect_args={"check_same_thread": False})


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info('{table}')")).fetchall()
    return any(row[1] == column for row in rows)


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table},
    ).fetchone()
    return row is not None


def _apply_lightweight_migrations() -> None:
    with engine.begin() as conn:
        # template 表新增字段
        if _table_exists(conn, "template"):
            if not _column_exists(conn, "template", "official"):
                conn.execute(text("ALTER TABLE template ADD COLUMN official BOOLEAN DEFAULT 1"))
            if not _column_exists(conn, "template", "template_group"):
                conn.execute(text("ALTER TABLE template ADD COLUMN template_group TEXT DEFAULT '官方模板'"))
            if not _column_exists(conn, "template", "created_at"):
                conn.execute(text("ALTER TABLE template ADD COLUMN created_at DATETIME"))

        # workflow 表新增字段
        if _table_exists(conn, "workflow"):
            if not _column_exists(conn, "workflow", "slo_profile"):
                conn.execute(text("ALTER TABLE workflow ADD COLUMN slo_profile TEXT"))
            if not _column_exists(conn, "workflow", "slo_overrides"):
                conn.execute(text("ALTER TABLE workflow ADD COLUMN slo_overrides JSON"))

        # run 表新增字段
        if _table_exists(conn, "run"):
            if not _column_exists(conn, "run", "updated_at"):
                conn.execute(text("ALTER TABLE run ADD COLUMN updated_at DATETIME"))
            if not _column_exists(conn, "run", "observability"):
                conn.execute(text("ALTER TABLE run ADD COLUMN observability JSON"))

        # runlog 表新增字段
        if _table_exists(conn, "runlog"):
            if not _column_exists(conn, "runlog", "error_code"):
                conn.execute(text("ALTER TABLE runlog ADD COLUMN error_code TEXT"))
            if not _column_exists(conn, "runlog", "detail"):
                conn.execute(text("ALTER TABLE runlog ADD COLUMN detail JSON"))

        # workflownodestate 表新增字段
        if _table_exists(conn, "workflownodestate") and not _column_exists(conn, "workflownodestate", "error_code"):
            conn.execute(text("ALTER TABLE workflownodestate ADD COLUMN error_code TEXT"))

        # uploadedartifact 表新增字段
        if _table_exists(conn, "uploadedartifact"):
            if not _column_exists(conn, "uploadedartifact", "content_type"):
                conn.execute(text("ALTER TABLE uploadedartifact ADD COLUMN content_type TEXT"))
            if not _column_exists(conn, "uploadedartifact", "sha256"):
                conn.execute(text("ALTER TABLE uploadedartifact ADD COLUMN sha256 TEXT"))
            if not _column_exists(conn, "uploadedartifact", "logical_key"):
                conn.execute(text("ALTER TABLE uploadedartifact ADD COLUMN logical_key TEXT DEFAULT 'default'"))
            if not _column_exists(conn, "uploadedartifact", "version"):
                conn.execute(text("ALTER TABLE uploadedartifact ADD COLUMN version INTEGER DEFAULT 1"))
            if not _column_exists(conn, "uploadedartifact", "is_active"):
                conn.execute(text("ALTER TABLE uploadedartifact ADD COLUMN is_active BOOLEAN DEFAULT 1"))
            if not _column_exists(conn, "uploadedartifact", "parent_artifact_id"):
                conn.execute(text("ALTER TABLE uploadedartifact ADD COLUMN parent_artifact_id TEXT"))
            if not _column_exists(conn, "uploadedartifact", "audit"):
                conn.execute(text("ALTER TABLE uploadedartifact ADD COLUMN audit JSON"))


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _apply_lightweight_migrations()


@contextmanager
def get_session_ctx():
    with Session(engine) as session:
        yield session


def get_session():
    with Session(engine) as session:
        yield session
