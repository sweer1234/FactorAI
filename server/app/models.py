from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def now_utc() -> datetime:
    return datetime.utcnow()


class Workflow(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    name: str
    category: str
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    status: str = Field(default="draft")
    updated_at: datetime = Field(default_factory=now_utc)
    last_run: datetime | None = None
    description: str | None = None
    owner_id: str | None = Field(default=None, index=True)
    source_template_id: str | None = None
    slo_profile: str | None = Field(default=None, index=True)
    slo_overrides: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    graph: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)


class Template(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    name: str
    description: str
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=now_utc)
    category: str
    official: bool = Field(default=True)
    template_group: str = Field(default="官方模板")
    graph: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)


class TemplateVersion(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    template_id: str = Field(index=True)
    version: str
    changelog: str = Field(default="")
    graph: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)


class NodeSpec(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    name: str
    category: str = Field(index=True)
    description: str
    inputs: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    outputs: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    params: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    doc: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    runtime: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=now_utc)


class Run(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    workflow_id: str = Field(index=True)
    workflow_name: str
    status: str = Field(default="queued")
    duration: str = Field(default="00m 00s")
    created_at: datetime = Field(default_factory=now_utc)
    owner_id: str | None = Field(default=None, index=True)
    message: str = Field(default="")
    logs: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    observability: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    cancel_requested: bool = Field(default=False, index=True)
    retried_from_run_id: str | None = Field(default=None, index=True)
    retry_origin_run_id: str | None = Field(default=None, index=True)
    retry_attempt: int = Field(default=1)
    retry_max_attempts: int = Field(default=1)
    retry_strategy: str = Field(default="immediate")
    retry_backoff_sec: int = Field(default=0)
    updated_at: datetime = Field(default_factory=now_utc)


class RunLog(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    run_id: str = Field(index=True)
    workflow_id: str = Field(index=True)
    level: str = Field(default="INFO")
    node_id: str | None = None
    node_name: str | None = None
    error_code: str | None = Field(default=None, index=True)
    detail: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    message: str
    created_at: datetime = Field(default_factory=now_utc)


class WorkflowNodeState(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    run_id: str = Field(index=True)
    workflow_id: str = Field(index=True)
    node_id: str = Field(index=True)
    node_name: str
    status: str = Field(default="queued")
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int = Field(default=0)
    error_code: str | None = Field(default=None, index=True)
    message: str = Field(default="")


class UploadedArtifact(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    workflow_id: str | None = Field(default=None, index=True)
    kind: str = Field(default="generic", index=True)
    logical_key: str = Field(default="default", index=True)
    version: int = Field(default=1, index=True)
    is_active: bool = Field(default=True, index=True)
    parent_artifact_id: str | None = Field(default=None, index=True)
    file_name: str
    file_size: int = Field(default=0)
    content_type: str | None = None
    sha256: str | None = Field(default=None, index=True)
    audit: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    file_path: str
    created_at: datetime = Field(default_factory=now_utc)


class Report(SQLModel, table=True):
    workflow_id: str = Field(primary_key=True, index=True)
    workflow_name: str
    metrics: list[dict[str, str]] = Field(default_factory=list, sa_column=Column(JSON))
    equity_series: list[float] = Field(default_factory=list, sa_column=Column(JSON))
    layer_return: list[dict[str, float | str]] = Field(default_factory=list, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=now_utc)


class RunMetricPoint(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    run_id: str = Field(index=True)
    workflow_id: str = Field(index=True)
    metric_name: str = Field(index=True)
    value: float = Field(default=0.0)
    tags: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)


class WorkflowGraphRevision(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    workflow_id: str = Field(index=True)
    revision_no: int = Field(default=1, index=True)
    source: str = Field(default="graph_update", index=True)
    graph: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    meta: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)
