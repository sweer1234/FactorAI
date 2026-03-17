from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    position: dict[str, float]
    styleVariant: str | None = None


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    animated: bool | None = None


class WorkflowGraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class WorkflowCreate(BaseModel):
    name: str
    category: str
    tags: list[str] = Field(default_factory=list)
    description: str | None = None
    graph: WorkflowGraph | None = None
    source_template_id: str | None = None


class WorkflowRead(BaseModel):
    id: str
    name: str
    category: str
    tags: list[str]
    status: str
    updated_at: datetime
    last_run: datetime | None = None
    description: str | None = None
    source_template_id: str | None = None
    graph: WorkflowGraph


class GraphUpdate(BaseModel):
    graph: WorkflowGraph


class TemplateRead(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str]
    updated_at: datetime
    category: str
    official: bool
    template_group: str
    graph: WorkflowGraph


class RunRead(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str
    status: str
    duration: str
    created_at: datetime
    message: str
    logs: list[str]


class RunLogRead(BaseModel):
    id: str
    run_id: str
    workflow_id: str
    level: str
    node_id: str | None = None
    node_name: str | None = None
    message: str
    created_at: datetime


class NodeStateRead(BaseModel):
    id: str
    run_id: str
    workflow_id: str
    node_id: str
    node_name: str
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int
    message: str


class ReportRead(BaseModel):
    workflow_id: str
    workflow_name: str
    metrics: list[dict[str, str]]
    equity_series: list[float]
    layer_return: list[dict[str, float | str]]
    updated_at: datetime


class NodeDefinitionRead(BaseModel):
    id: str
    name: str
    category: str
    description: str
    inputs: list[str]
    outputs: list[str]
    params: list[dict[str, Any]]
    doc: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)
