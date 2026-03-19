from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    position: dict[str, float]
    styleVariant: str | None = None
    nodeSpecId: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


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
    slo_profile: str | None = None
    slo_overrides: dict[str, int | float] = Field(default_factory=dict)
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
    observability: dict[str, Any] = Field(default_factory=dict)


class RunLogRead(BaseModel):
    id: str
    run_id: str
    workflow_id: str
    level: str
    node_id: str | None = None
    node_name: str | None = None
    error_code: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
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
    error_code: str | None = None
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


class ArtifactRead(BaseModel):
    id: str
    workflow_id: str | None = None
    kind: str
    logical_key: str
    version: int
    is_active: bool
    parent_artifact_id: str | None = None
    file_name: str
    file_size: int
    content_type: str | None = None
    sha256: str | None = None
    audit: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ArtifactRollbackRequest(BaseModel):
    reason: str | None = None


class RunObservabilityRead(BaseModel):
    run_id: str
    workflow_id: str
    summary: dict[str, Any] = Field(default_factory=dict)


class RunAlertsRead(BaseModel):
    run_id: str
    workflow_id: str
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    thresholds: dict[str, int | float] = Field(default_factory=dict)


class RunMetricPointRead(BaseModel):
    id: str
    run_id: str
    workflow_id: str
    metric_name: str
    value: float
    tags: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ContractIssueRead(BaseModel):
    code: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


class ContractFixSuggestionRead(BaseModel):
    issue_code: str
    priority: str
    title: str
    message: str
    proposed_action: str
    patch: dict[str, Any] = Field(default_factory=dict)


class ContractCompileRead(BaseModel):
    valid: bool
    strict: bool
    errors: list[ContractIssueRead] = Field(default_factory=list)
    warnings: list[ContractIssueRead] = Field(default_factory=list)
    suggestions: list[ContractFixSuggestionRead] = Field(default_factory=list)
    node_input_schemas: dict[str, dict[str, dict[str, Any]]] = Field(default_factory=dict)
    node_output_schemas: dict[str, dict[str, dict[str, Any]]] = Field(default_factory=dict)
    compiled_at: datetime


class ContractFixApplyRequest(BaseModel):
    strict: bool = False
    suggestion_indexes: list[int] = Field(default_factory=list)
    max_actions: int = 20


class ContractFixAppliedActionRead(BaseModel):
    index: int
    action: str
    status: str
    message: str
    patch: dict[str, Any] = Field(default_factory=dict)


class ContractFixApplyRead(BaseModel):
    workflow: WorkflowRead
    compile: ContractCompileRead
    applied_actions: list[ContractFixAppliedActionRead] = Field(default_factory=list)


class ContractFixRollbackRequest(BaseModel):
    revision_id: str | None = None


class ContractFixRollbackRead(BaseModel):
    workflow: WorkflowRead
    compile: ContractCompileRead
    restored_revision_id: str
    applied_actions: list[ContractFixAppliedActionRead] = Field(default_factory=list)


class GraphRevisionRead(BaseModel):
    id: str
    workflow_id: str
    revision_no: int
    source: str
    meta: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class SLOConfigUpdateRequest(BaseModel):
    profile: str | None = None
    overrides: dict[str, int | float] = Field(default_factory=dict)


class RunCompareRead(BaseModel):
    workflow_id: str
    run_ids: list[str] = Field(default_factory=list)
    metrics: dict[str, dict[str, float | int | str | None]] = Field(default_factory=dict)


class TrendPointRead(BaseModel):
    run_id: str
    created_at: str
    status: str
    value: float
    threshold: float | None = None


class WorkflowTrendRead(BaseModel):
    workflow_id: str
    metrics: list[str] = Field(default_factory=list)
    run_ids: list[str] = Field(default_factory=list)
    thresholds: dict[str, int | float] = Field(default_factory=dict)
    points: dict[str, list[TrendPointRead]] = Field(default_factory=dict)


class SLOViewRead(BaseModel):
    workflow_id: str
    window_size: int
    thresholds: dict[str, int | float] = Field(default_factory=dict)
    pass_rate: float
    pass_count: int
    fail_count: int
    runs: list[dict[str, Any]] = Field(default_factory=list)


class SLOTemplateRead(BaseModel):
    workflow_id: str
    workflow_category: str
    profile: str
    reason: str
    thresholds: dict[str, int | float] = Field(default_factory=dict)
