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
    source_template_id: str | None = None
    graph: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)


class Template(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    name: str
    description: str
    tags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=now_utc)
    category: str
    graph: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Run(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    workflow_id: str = Field(index=True)
    workflow_name: str
    status: str = Field(default="queued")
    duration: str = Field(default="00m 00s")
    created_at: datetime = Field(default_factory=now_utc)
    message: str = Field(default="")
    logs: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class Report(SQLModel, table=True):
    workflow_id: str = Field(primary_key=True, index=True)
    workflow_name: str
    metrics: list[dict[str, str]] = Field(default_factory=list, sa_column=Column(JSON))
    equity_series: list[float] = Field(default_factory=list, sa_column=Column(JSON))
    layer_return: list[dict[str, float | str]] = Field(default_factory=list, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=now_utc)
