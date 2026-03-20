from datetime import datetime
from typing import Any, Literal

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
    owner_id: str | None = None
    run_policy: dict[str, Any] = Field(default_factory=dict)
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
    owner_id: str | None = None
    official: bool
    template_group: str
    is_subscribed: bool = False
    subscribed_count: int = 0
    graph: WorkflowGraph


class TemplatePublishRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)
    category: str | None = None
    template_group: str | None = None
    official: bool = False


class TemplateVersionRead(BaseModel):
    id: str
    template_id: str
    version: str
    changelog: str
    graph: WorkflowGraph
    created_at: datetime


class TemplateVersionCreateRequest(BaseModel):
    version: str | None = None
    changelog: str = ""


class TemplateVersionRollbackRequest(BaseModel):
    version: str | None = None
    version_id: str | None = None
    changelog: str = "rollback to previous version"


class TemplateVersionRollbackRead(BaseModel):
    template: TemplateRead
    restored_version: TemplateVersionRead
    created_version: TemplateVersionRead


class TemplateVersionDiffRead(BaseModel):
    template_id: str
    from_version: str
    to_version: str
    summary: dict[str, int] = Field(default_factory=dict)
    added_nodes: list[str] = Field(default_factory=list)
    removed_nodes: list[str] = Field(default_factory=list)
    changed_nodes: list[str] = Field(default_factory=list)
    added_edges: list[str] = Field(default_factory=list)
    removed_edges: list[str] = Field(default_factory=list)


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
    owner_id: str | None = None
    cancel_requested: bool = False
    retried_from_run_id: str | None = None
    retry_origin_run_id: str | None = None
    retry_attempt: int = 1
    retry_max_attempts: int = 1
    retry_strategy: str = "immediate"
    retry_backoff_sec: int = 0


class RunRetryRequest(BaseModel):
    strategy: Literal["immediate", "fixed_backoff"] = "immediate"
    max_attempts: int = Field(default=1, ge=1, le=5)
    backoff_sec: int = Field(default=0, ge=0, le=300)


class RunBatchActionRequest(BaseModel):
    action: Literal["cancel", "retry"]
    run_ids: list[str] = Field(default_factory=list)
    retry: RunRetryRequest | None = None


class RunBatchActionItemRead(BaseModel):
    run_id: str
    status: str
    message: str
    new_run_id: str | None = None


class RunBatchActionRead(BaseModel):
    action: str
    total: int
    success: int
    failed: int
    items: list[RunBatchActionItemRead] = Field(default_factory=list)


class WorkflowRunPolicyRead(BaseModel):
    workflow_id: str
    strategy: Literal["immediate", "fixed_backoff"] = "immediate"
    max_attempts: int = Field(default=1, ge=1, le=5)
    backoff_sec: int = Field(default=0, ge=0, le=300)


class WorkflowRunPolicyUpdateRequest(BaseModel):
    strategy: Literal["immediate", "fixed_backoff"] = "immediate"
    max_attempts: int = Field(default=1, ge=1, le=5)
    backoff_sec: int = Field(default=0, ge=0, le=300)


class AuthUserRead(BaseModel):
    user_id: str
    role: str
    token: str


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


class AlertIncidentRead(BaseModel):
    run_id: str
    created_at: str
    status: str
    alerts: list[dict[str, Any]] = Field(default_factory=list)


class WorkflowAlertsRead(BaseModel):
    workflow_id: str
    window_size: int
    thresholds: dict[str, int | float] = Field(default_factory=dict)
    total_runs: int
    alert_runs: int
    counts: dict[str, int] = Field(default_factory=dict)
    incidents: list[AlertIncidentRead] = Field(default_factory=list)


class ObservabilityRecommendationRead(BaseModel):
    code: str
    level: str
    message: str
    action: str


class WorkflowInsightsRead(BaseModel):
    workflow_id: str
    window_size: int
    health_score: int
    health_level: str
    pass_rate: float
    alert_runs: int
    total_runs: int
    latest_run_id: str | None = None
    latest_summary: dict[str, int | float | str | None] = Field(default_factory=dict)
    thresholds: dict[str, int | float] = Field(default_factory=dict)
    suggested_slo_config: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[ObservabilityRecommendationRead] = Field(default_factory=list)


class ObservabilityAnomalyRead(BaseModel):
    run_id: str
    metric_name: str
    value: float
    baseline: float
    z_score: float
    level: str
    status: str
    created_at: str
    message: str


class WorkflowAnomaliesRead(BaseModel):
    workflow_id: str
    window_size: int
    z_threshold: float
    metrics: list[str] = Field(default_factory=list)
    total_runs: int
    anomaly_count: int
    anomaly_by_metric: dict[str, int] = Field(default_factory=dict)
    anomalies: list[ObservabilityAnomalyRead] = Field(default_factory=list)


class ObservabilityReportRead(BaseModel):
    workflow_id: str
    window_size: int
    generated_at: str
    markdown: str


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
