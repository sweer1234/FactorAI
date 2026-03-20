from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
from pathlib import Path
import statistics
from typing import Any
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
import networkx as nx
from sqlmodel import Session, select

from .config import settings
from .db import get_session
from .models import NodeSpec, Report, Run, RunLog, Template, TemplateVersion, UploadedArtifact, Workflow, WorkflowGraphRevision
from .security import AuthUser, require_request_access, require_role
from .schemas import (
    AlertIncidentRead,
    ArtifactRead,
    ArtifactRollbackRequest,
    ContractCompileRead,
    ContractFixApplyRead,
    ContractFixApplyRequest,
    ContractFixAppliedActionRead,
    ContractFixRollbackRead,
    ContractFixRollbackRequest,
    ContractFixSuggestionRead,
    GraphRevisionRead,
    GraphUpdate,
    ContractIssueRead,
    AuthUserRead,
    NodeDefinitionRead,
    NodeStateRead,
    ReportRead,
    RunAlertsRead,
    RunCompareRead,
    RunMetricPointRead,
    ObservabilityRecommendationRead,
    ObservabilityAnomalyRead,
    ObservabilityReportRead,
    SLOConfigUpdateRequest,
    SLOTemplateRead,
    SLOViewRead,
    TrendPointRead,
    RunLogRead,
    RunObservabilityRead,
    RunRetryRequest,
    RunRead,
    TemplateRead,
    TemplateVersionCreateRequest,
    TemplateVersionDiffRead,
    TemplateVersionRead,
    TemplateVersionRollbackRead,
    TemplateVersionRollbackRequest,
    WorkflowAlertsRead,
    WorkflowAnomaliesRead,
    WorkflowInsightsRead,
    WorkflowTrendRead,
    WorkflowCreate,
    WorkflowRead,
)
from .services.contract import compile_workflow_contract
from .services.execution import (
    cancel_run,
    get_run_alerts,
    get_run_observability,
    list_node_states,
    list_run_logs,
    list_run_metric_points,
    list_runs,
    list_workflow_metric_points,
    retry_run,
    start_run,
)
from .services.node_library import NODE_LIBRARY
from .services.slo import DEFAULT_THRESHOLDS, PROFILE_THRESHOLDS, resolve_slo_profile


router = APIRouter(dependencies=[Depends(require_request_access)])


def _is_admin(user: AuthUser) -> bool:
    return user.role == "admin"


def _can_access_owner(owner_id: str | None, user: AuthUser) -> bool:
    if _is_admin(user):
        return True
    if not owner_id:
        return True
    return owner_id == user.user_id


def _ensure_workflow_access(
    session: Session,
    workflow_id: str,
    user: AuthUser,
) -> Workflow:
    row = session.get(Workflow, workflow_id)
    if not row:
        raise HTTPException(status_code=404, detail="workflow not found")
    if not _can_access_owner(row.owner_id, user):
        raise HTTPException(status_code=403, detail="forbidden: workflow access denied")
    return row


def _ensure_run_access(session: Session, run_id: str, user: AuthUser) -> Run:
    row = session.get(Run, run_id)
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    if not _can_access_owner(row.owner_id, user):
        raise HTTPException(status_code=403, detail="forbidden: run access denied")
    return row


def _graph_version_diff(from_graph: dict[str, Any], to_graph: dict[str, Any]) -> TemplateVersionDiffRead:
    from_nodes = {str(item.get("id")): str(item.get("label") or item.get("id")) for item in (from_graph or {}).get("nodes", [])}
    to_nodes = {str(item.get("id")): str(item.get("label") or item.get("id")) for item in (to_graph or {}).get("nodes", [])}
    from_edges = {f"{item.get('source')}->{item.get('target')}" for item in (from_graph or {}).get("edges", [])}
    to_edges = {f"{item.get('source')}->{item.get('target')}" for item in (to_graph or {}).get("edges", [])}

    added_node_ids = sorted([item for item in to_nodes if item not in from_nodes])
    removed_node_ids = sorted([item for item in from_nodes if item not in to_nodes])
    changed_node_ids = sorted([item for item in to_nodes if item in from_nodes and to_nodes[item] != from_nodes[item]])
    added_edges = sorted([item for item in to_edges if item not in from_edges])
    removed_edges = sorted([item for item in from_edges if item not in to_edges])
    return TemplateVersionDiffRead(
        template_id="",
        from_version="",
        to_version="",
        summary={
            "from_nodes": len(from_nodes),
            "to_nodes": len(to_nodes),
            "from_edges": len(from_edges),
            "to_edges": len(to_edges),
            "added_nodes": len(added_node_ids),
            "removed_nodes": len(removed_node_ids),
            "changed_nodes": len(changed_node_ids),
            "added_edges": len(added_edges),
            "removed_edges": len(removed_edges),
        },
        added_nodes=[to_nodes[item] for item in added_node_ids],
        removed_nodes=[from_nodes[item] for item in removed_node_ids],
        changed_nodes=[f"{from_nodes[item]} -> {to_nodes[item]}" for item in changed_node_ids],
        added_edges=added_edges,
        removed_edges=removed_edges,
    )


def _workflow_to_read(row: Workflow) -> WorkflowRead:
    return WorkflowRead(
        id=row.id,
        name=row.name,
        category=row.category,
        tags=row.tags,
        status=row.status,
        updated_at=row.updated_at,
        last_run=row.last_run,
        description=row.description,
        owner_id=row.owner_id,
        source_template_id=row.source_template_id,
        slo_profile=row.slo_profile,
        slo_overrides={key: float(value) for key, value in (row.slo_overrides or {}).items()},
        graph=row.graph or {"nodes": [], "edges": []},
    )


def _template_to_read(row: Template) -> TemplateRead:
    return TemplateRead(
        id=row.id,
        name=row.name,
        description=row.description,
        tags=row.tags,
        updated_at=row.updated_at,
        category=row.category,
        official=row.official,
        template_group=row.template_group,
        graph=row.graph or {"nodes": [], "edges": []},
    )


def _template_version_to_read(row: TemplateVersion) -> TemplateVersionRead:
    return TemplateVersionRead(
        id=row.id,
        template_id=row.template_id,
        version=row.version,
        changelog=row.changelog,
        graph=row.graph or {"nodes": [], "edges": []},
        created_at=row.created_at,
    )


def _next_template_version(existing_versions: list[str]) -> str:
    semver_parts: list[tuple[int, int, int]] = []
    for item in existing_versions:
        parts = item.split(".")
        if len(parts) != 3:
            continue
        try:
            semver_parts.append((int(parts[0]), int(parts[1]), int(parts[2])))
        except ValueError:
            continue
    if not semver_parts:
        return f"1.0.{len(existing_versions) + 1}"
    major, minor, patch = sorted(semver_parts)[-1]
    return f"{major}.{minor}.{patch + 1}"


def _run_to_read(row: Run) -> RunRead:
    return RunRead(
        id=row.id,
        workflow_id=row.workflow_id,
        workflow_name=row.workflow_name,
        status=row.status,
        duration=row.duration,
        created_at=row.created_at,
        message=row.message,
        logs=row.logs,
        observability=row.observability or {},
        owner_id=row.owner_id,
        cancel_requested=bool(row.cancel_requested),
        retried_from_run_id=row.retried_from_run_id,
        retry_origin_run_id=row.retry_origin_run_id,
        retry_attempt=int(row.retry_attempt or 1),
        retry_max_attempts=int(row.retry_max_attempts or 1),
        retry_strategy=row.retry_strategy or "immediate",
        retry_backoff_sec=int(row.retry_backoff_sec or 0),
    )


def _nodespec_to_read(row: NodeSpec | dict) -> NodeDefinitionRead:
    if isinstance(row, dict):
        return NodeDefinitionRead(**row)
    return NodeDefinitionRead(
        id=row.id,
        name=row.name,
        category=row.category,
        description=row.description,
        inputs=row.inputs,
        outputs=row.outputs,
        params=row.params,
        doc=row.doc,
        runtime=row.runtime,
    )


def _artifact_to_read(row: UploadedArtifact) -> ArtifactRead:
    return ArtifactRead(
        id=row.id,
        workflow_id=row.workflow_id,
        kind=row.kind,
        logical_key=row.logical_key or "default",
        version=int(row.version or 1),
        is_active=bool(row.is_active),
        parent_artifact_id=row.parent_artifact_id,
        file_name=row.file_name,
        file_size=row.file_size,
        content_type=row.content_type,
        sha256=row.sha256,
        audit=row.audit or {},
        created_at=row.created_at,
    )


def _next_graph_revision_no(session: Session, workflow_id: str) -> int:
    row = session.exec(
        select(WorkflowGraphRevision.revision_no)
        .where(WorkflowGraphRevision.workflow_id == workflow_id)
        .order_by(WorkflowGraphRevision.revision_no.desc())
    ).first()
    return int(row or 0) + 1


def _create_graph_revision(
    session: Session,
    workflow_id: str,
    *,
    source: str,
    graph: dict[str, Any],
    meta: dict[str, Any] | None = None,
) -> WorkflowGraphRevision:
    revision = WorkflowGraphRevision(
        id=f"wgr-{uuid.uuid4().hex[:10]}",
        workflow_id=workflow_id,
        revision_no=_next_graph_revision_no(session, workflow_id),
        source=source,
        graph=deepcopy(graph or {"nodes": [], "edges": []}),
        meta=meta or {},
        created_at=datetime.utcnow(),
    )
    session.add(revision)
    return revision


def _style_variant_by_category(category: str) -> str:
    if category.startswith("01"):
        return "data"
    if category.startswith("02"):
        return "feature"
    if category.startswith("03"):
        return "model"
    if category.startswith("04"):
        return "factor"
    if category.startswith("05"):
        return "backtest"
    return "default"


def _nodespec_map(session: Session) -> dict[str, dict[str, Any]]:
    node_specs = list(session.exec(select(NodeSpec)))
    return {
        item.id: {
            "id": item.id,
            "name": item.name,
            "category": item.category,
            "inputs": item.inputs,
            "outputs": item.outputs,
            "params": item.params,
        }
        for item in node_specs
    }


def _to_compile_read(result: dict[str, Any], strict: bool) -> ContractCompileRead:
    return ContractCompileRead(
        valid=result.get("valid", False),
        strict=result.get("strict", strict),
        errors=[ContractIssueRead(**item) for item in result.get("errors", [])],
        warnings=[ContractIssueRead(**item) for item in result.get("warnings", [])],
        suggestions=[ContractFixSuggestionRead(**item) for item in result.get("suggestions", [])],
        node_input_schemas=result.get("node_input_schemas", {}),
        node_output_schemas=result.get("node_output_schemas", {}),
        compiled_at=datetime.utcnow(),
    )


def _resolve_slo_thresholds(
    workflow: Workflow,
    *,
    use_template: bool,
    profile: str | None,
    overrides: dict[str, int | None],
) -> dict[str, int]:
    base = dict(DEFAULT_THRESHOLDS)
    if use_template:
        preferred_profile = profile or workflow.slo_profile
        template = resolve_slo_profile(workflow.category, workflow.tags, preferred_profile=preferred_profile)
        base.update({key: int(value) for key, value in template.get("thresholds", {}).items()})
    base.update({key: int(value) for key, value in (workflow.slo_overrides or {}).items()})
    for key, value in overrides.items():
        if value is not None:
            base[key] = int(value)
    return base


def _build_insight_recommendations(
    *,
    pass_rate: float,
    latest_summary: dict[str, int | float | str | None],
    thresholds: dict[str, int],
    alert_runs: int,
) -> list[dict[str, str]]:
    recommendations: list[dict[str, str]] = []
    latest_p95 = float(latest_summary.get("p95_node_duration_ms", 0) or 0)
    latest_failed = int(latest_summary.get("failed_nodes", 0) or 0)
    latest_warn = int(latest_summary.get("warn_logs", 0) or 0)
    latest_error = int(latest_summary.get("error_logs", 0) or 0)

    if pass_rate < 0.8:
        recommendations.append(
            {
                "code": "R_LOW_SLO_PASS_RATE",
                "level": "error",
                "message": f"SLO 通过率偏低（{pass_rate * 100:.1f}%），建议优先处理高频失败与高耗时节点。",
                "action": "查看运行失败原因聚合，优先处理前2位失败节点，再重跑验证。",
            }
        )
    if latest_p95 > float(thresholds.get("p95_node_duration_ms", 0)):
        recommendations.append(
            {
                "code": "R_P95_TOO_SLOW",
                "level": "warn",
                "message": f"P95 节点耗时超阈值（{latest_p95:.0f}ms）。",
                "action": "在编辑器日志中定位慢节点，减少输入字段或拆分节点并开启制品复用。",
            }
        )
    if latest_failed > int(thresholds.get("failed_nodes", 0)):
        recommendations.append(
            {
                "code": "R_FAILED_NODES",
                "level": "error",
                "message": f"失败节点数超阈值（{latest_failed}）。",
                "action": "使用“修复历史回滚”回到稳定版本，并重新应用自动修复建议。",
            }
        )
    if latest_warn > int(thresholds.get("warn_logs", 0)) or latest_error > int(thresholds.get("error_logs", 0)):
        recommendations.append(
            {
                "code": "R_LOG_ALERTS",
                "level": "warn",
                "message": "运行日志告警/错误偏多，存在潜在数据契约或输入质量问题。",
                "action": "检查 SLO 告警时间线，先清理重复 WARN 来源，再调整阈值策略。",
            }
        )
    if alert_runs > 0:
        recommendations.append(
            {
                "code": "R_ALERT_INCIDENTS",
                "level": "warn",
                "message": f"最近窗口内出现 {alert_runs} 次告警事件。",
                "action": "在报告页告警事件时间线中按告警码聚类，逐项制定消警动作。",
            }
        )
    if not recommendations:
        recommendations.append(
            {
                "code": "R_HEALTHY",
                "level": "info",
                "message": "近期运行健康，建议保持当前阈值与工作流结构。",
                "action": "可适度收紧阈值提升质量基线。",
            }
        )
    return recommendations


def _build_suggested_slo_config(
    *,
    pass_rate: float,
    latest_summary: dict[str, int | float | str | None],
    thresholds: dict[str, int],
) -> dict[str, Any]:
    overrides: dict[str, int] = {}
    latest_p95 = int(latest_summary.get("p95_node_duration_ms", 0) or 0)
    latest_warn = int(latest_summary.get("warn_logs", 0) or 0)
    latest_error = int(latest_summary.get("error_logs", 0) or 0)
    latest_failed = int(latest_summary.get("failed_nodes", 0) or 0)

    current_p95 = int(thresholds.get("p95_node_duration_ms", 800))
    current_warn = int(thresholds.get("warn_logs", 20))
    current_error = int(thresholds.get("error_logs", 0))

    # 通过率低但失败节点不高时，优先放宽噪声阈值，降低误报。
    if pass_rate < 0.75 and latest_failed == 0:
        if latest_p95 > current_p95:
            overrides["p95_node_duration_ms"] = max(current_p95, int(latest_p95 * 1.15))
        if latest_warn > current_warn:
            overrides["warn_logs"] = max(current_warn, int(latest_warn * 1.2))
        if latest_error > current_error:
            overrides["error_logs"] = max(current_error, latest_error)

    # 通过率很高时，建议略微收紧，提升质量基线。
    if pass_rate > 0.95:
        overrides["p95_node_duration_ms"] = max(100, int(current_p95 * 0.9))

    return {
        "profile": None,
        "overrides": overrides,
        "reason": "auto_from_insights",
    }


def _robust_z_scores(values: list[float]) -> tuple[float, float, list[float]]:
    if not values:
        return 0.0, 0.0, []
    baseline = float(statistics.median(values))
    deviations = [abs(item - baseline) for item in values]
    mad = float(statistics.median(deviations)) if deviations else 0.0
    if mad > 1e-12:
        z_scores = [0.6745 * (item - baseline) / mad for item in values]
        return baseline, mad, z_scores
    std = float(statistics.pstdev(values)) if len(values) > 1 else 0.0
    if std <= 1e-12:
        return baseline, 0.0, [0.0 for _ in values]
    z_scores = [(item - baseline) / std for item in values]
    return baseline, std, z_scores


def _apply_contract_suggestions(
    graph: dict[str, Any],
    nodespec_map: dict[str, dict[str, Any]],
    suggestions: list[dict[str, Any]],
    *,
    suggestion_indexes: list[int],
    max_actions: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    draft = deepcopy(graph or {})
    nodes = [dict(item) for item in draft.get("nodes", [])]
    edges = [dict(item) for item in draft.get("edges", [])]
    node_order = [item.get("id") for item in nodes if item.get("id")]
    node_map = {item["id"]: item for item in nodes if item.get("id")}
    edge_pairs = {(item.get("source"), item.get("target")) for item in edges}
    used_indexes: set[int] = set()
    selected: list[tuple[int, dict[str, Any]]] = []

    if suggestion_indexes:
        for index in suggestion_indexes:
            if 0 <= index < len(suggestions) and index not in used_indexes:
                selected.append((index, suggestions[index]))
                used_indexes.add(index)
    else:
        selected = list(enumerate(suggestions))

    selected = selected[: max(1, min(200, max_actions))]
    applied_actions: list[dict[str, Any]] = []

    def _would_create_cycle(source: str, target: str) -> bool:
        if source == target:
            return True
        dag = nx.DiGraph()
        for item in node_map:
            dag.add_node(item)
        for edge in edges:
            src = str(edge.get("source") or "")
            dst = str(edge.get("target") or "")
            if src and dst:
                dag.add_edge(src, dst)
        dag.add_edge(source, target)
        return not nx.is_directed_acyclic_graph(dag)

    for index, item in selected:
        action = str(item.get("proposed_action", "unknown"))
        patch = dict(item.get("patch") or {})
        status = "skipped"
        message = "当前建议类型暂未支持自动应用"

        if action == "connect_edge":
            source = str(patch.get("source") or "")
            target = str(patch.get("target") or "")
            if source in node_map and target in node_map:
                if (source, target) in edge_pairs:
                    message = "连线已存在，跳过"
                elif _would_create_cycle(source, target):
                    message = "该连线会引入环路，已跳过"
                else:
                    edges.append(
                        {
                            "id": f"e-auto-{uuid.uuid4().hex[:8]}",
                            "source": source,
                            "target": target,
                            "animated": True,
                        }
                    )
                    edge_pairs.add((source, target))
                    status = "applied"
                    message = "已新增建议连线"
            else:
                message = "源节点或目标节点不存在，无法应用"

        elif action in {"upgrade_schema_version", "upgrade_schema_or_insert_transform"}:
            target = str(patch.get("target") or "")
            params_patch = dict(patch.get("params_patch") or {})
            if target in node_map:
                node = dict(node_map[target])
                node_params = dict(node.get("params") or {})
                node_params.update(params_patch)
                node["params"] = node_params
                node_map[target] = node
                status = "applied"
                message = "已更新节点参数补丁"
            else:
                message = "目标节点不存在，无法应用参数补丁"

        if action in {"insert_adapter_node", "upgrade_schema_or_insert_transform"}:
            adapter_spec_id = str(patch.get("adapter_node_spec_id") or "feature.build")
            target = str(patch.get("target") or "")
            if adapter_spec_id in nodespec_map and target in node_map:
                spec = nodespec_map[adapter_spec_id]
                target_node = node_map[target]
                target_position = target_node.get("position") or {"x": 400, "y": 220}
                adapter_id = f"n-auto-{uuid.uuid4().hex[:8]}"
                adapter_params = {
                    str(param.get("key")): param.get("defaultValue")
                    for param in spec.get("params", [])
                    if param.get("key")
                }
                adapter_node = {
                    "id": adapter_id,
                    "label": spec.get("name", adapter_spec_id),
                    "position": {
                        "x": float(target_position.get("x", 400)) - 210,
                        "y": float(target_position.get("y", 220)) - 20,
                    },
                    "styleVariant": _style_variant_by_category(str(spec.get("category", ""))),
                    "nodeSpecId": adapter_spec_id,
                    "params": adapter_params,
                }
                node_map[adapter_id] = adapter_node
                node_order.append(adapter_id)
                incoming = [edge for edge in edges if edge.get("target") == target]
                source = str(patch.get("source") or (incoming[0].get("source") if incoming else ""))
                if (
                    source
                    and source in node_map
                    and (source, adapter_id) not in edge_pairs
                    and not _would_create_cycle(source, adapter_id)
                ):
                    edges.append(
                        {
                            "id": f"e-auto-{uuid.uuid4().hex[:8]}",
                            "source": source,
                            "target": adapter_id,
                            "animated": True,
                        }
                    )
                    edge_pairs.add((source, adapter_id))
                if (adapter_id, target) not in edge_pairs and not _would_create_cycle(adapter_id, target):
                    edges.append(
                        {
                            "id": f"e-auto-{uuid.uuid4().hex[:8]}",
                            "source": adapter_id,
                            "target": target,
                            "animated": True,
                        }
                    )
                    edge_pairs.add((adapter_id, target))
                status = "applied"
                message = "已插入适配节点并建立连线"
            elif status != "applied":
                message = "适配节点规格或目标节点缺失，无法插入"

        if action == "add_column_mapping":
            target = str(patch.get("target") or "")
            missing_columns = [str(item) for item in patch.get("missing_columns", []) if str(item)]
            if target in node_map:
                node = dict(node_map[target])
                node_params = dict(node.get("params") or {})
                node_params["autoColumnMapping"] = True
                if missing_columns:
                    node_params["requiredColumns"] = ",".join(missing_columns)
                node["params"] = node_params
                node_map[target] = node
                status = "applied"
                message = "已自动补充字段映射参数"
            else:
                message = "目标节点不存在，无法补齐字段映射"

        applied_actions.append(
            {
                "index": index,
                "action": action,
                "status": status,
                "message": message,
                "patch": patch,
            }
        )

    final_nodes = [node_map[node_id] for node_id in node_order if node_id in node_map]
    return {"nodes": final_nodes, "edges": edges}, applied_actions


@router.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@router.get("/auth/me", response_model=AuthUserRead)
def get_auth_me(current_user: AuthUser = Depends(require_request_access)):
    return AuthUserRead(
        user_id=current_user.user_id,
        role=current_user.role,
        token=current_user.token,
    )


@router.get("/node-library", response_model=list[NodeDefinitionRead])
def get_node_library(session: Session = Depends(get_session)):
    rows = list(session.exec(select(NodeSpec).order_by(NodeSpec.category.asc(), NodeSpec.name.asc())))
    if not rows:
        return [_nodespec_to_read(item) for item in NODE_LIBRARY]
    return [_nodespec_to_read(item) for item in rows]


@router.get("/node-specs", response_model=list[NodeDefinitionRead])
def get_node_specs(
    session: Session = Depends(get_session),
    category: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
):
    query = select(NodeSpec).order_by(NodeSpec.category.asc(), NodeSpec.name.asc())
    if category:
        query = query.where(NodeSpec.category == category)
    rows = list(session.exec(query))
    if keyword:
        key = keyword.lower()
        rows = [row for row in rows if key in row.name.lower() or key in row.description.lower()]
    return [_nodespec_to_read(item) for item in rows]


@router.get("/node-specs/{node_id}", response_model=NodeDefinitionRead)
def get_node_spec(node_id: str, session: Session = Depends(get_session)):
    row = session.get(NodeSpec, node_id)
    if not row:
        # fallback for compatibility
        fallback = next((item for item in NODE_LIBRARY if item["id"] == node_id), None)
        if fallback:
            return _nodespec_to_read(fallback)
        raise HTTPException(status_code=404, detail="node spec not found")
    return _nodespec_to_read(row)


@router.get("/workflows", response_model=list[WorkflowRead])
def get_workflows(
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    rows = list(session.exec(select(Workflow).order_by(Workflow.updated_at.desc())))
    if not _is_admin(current_user):
        rows = [row for row in rows if _can_access_owner(row.owner_id, current_user)]
    return [_workflow_to_read(row) for row in rows]


@router.get("/workflows/{workflow_id}", response_model=WorkflowRead)
def get_workflow(
    workflow_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    row = _ensure_workflow_access(session, workflow_id, current_user)
    return _workflow_to_read(row)


@router.post("/workflows", response_model=WorkflowRead)
def create_workflow(
    payload: WorkflowCreate,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    workflow = Workflow(
        id=f"wf-{uuid.uuid4().hex[:8]}",
        name=payload.name.strip(),
        category=payload.category.strip() or "未分类",
        tags=payload.tags,
        status="draft",
        updated_at=datetime.utcnow(),
        description=payload.description,
        owner_id=current_user.user_id,
        source_template_id=payload.source_template_id,
        graph=(payload.graph.model_dump() if payload.graph else {"nodes": [], "edges": []}),
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return _workflow_to_read(workflow)


@router.put("/workflows/{workflow_id}/graph", response_model=WorkflowRead)
def update_workflow_graph(
    workflow_id: str,
    payload: GraphUpdate,
    strict_contract: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    row = _ensure_workflow_access(session, workflow_id, current_user)
    nodespec_map = _nodespec_map(session)
    compile_result = compile_workflow_contract(payload.graph.model_dump(), nodespec_map, strict=strict_contract)
    if strict_contract and compile_result.get("errors"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "contract compile failed",
                "errors": compile_result["errors"],
                "suggestions": compile_result.get("suggestions", []),
            },
        )
    _create_graph_revision(
        session,
        row.id,
        source="graph_update",
        graph=row.graph or {"nodes": [], "edges": []},
        meta={
            "strict_contract": strict_contract,
            "errors": len(compile_result.get("errors", [])),
            "warnings": len(compile_result.get("warnings", [])),
        },
    )
    row.graph = payload.graph.model_dump()
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _workflow_to_read(row)


@router.post("/workflows/{workflow_id}/contract-fix-apply", response_model=ContractFixApplyRead)
def apply_contract_fix_suggestions(
    workflow_id: str,
    payload: ContractFixApplyRequest,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    row = _ensure_workflow_access(session, workflow_id, current_user)
    nodespec_map = _nodespec_map(session)
    compile_result = compile_workflow_contract(row.graph or {"nodes": [], "edges": []}, nodespec_map, strict=payload.strict)
    suggestions = compile_result.get("suggestions", [])
    if not suggestions:
        return ContractFixApplyRead(
            workflow=_workflow_to_read(row),
            compile=_to_compile_read(compile_result, strict=payload.strict),
            applied_actions=[],
        )
    next_graph, applied_actions = _apply_contract_suggestions(
        row.graph or {"nodes": [], "edges": []},
        nodespec_map,
        suggestions,
        suggestion_indexes=payload.suggestion_indexes,
        max_actions=payload.max_actions,
    )
    checkpoint = _create_graph_revision(
        session,
        row.id,
        source="contract_fix_apply",
        graph=row.graph or {"nodes": [], "edges": []},
        meta={
            "strict": payload.strict,
            "suggestion_indexes": payload.suggestion_indexes,
            "max_actions": payload.max_actions,
            "suggestions_count": len(suggestions),
            "applied_count": len([item for item in applied_actions if item.get("status") == "applied"]),
        },
    )
    for item in applied_actions:
        item.setdefault("patch", {})
        item["patch"]["checkpoint_revision_id"] = checkpoint.id
    row.graph = next_graph
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    compile_after = compile_workflow_contract(row.graph or {"nodes": [], "edges": []}, nodespec_map, strict=payload.strict)
    return ContractFixApplyRead(
        workflow=_workflow_to_read(row),
        compile=_to_compile_read(compile_after, strict=payload.strict),
        applied_actions=[ContractFixAppliedActionRead(**item) for item in applied_actions],
    )


@router.get("/workflows/{workflow_id}/contract-compile", response_model=ContractCompileRead)
def compile_workflow_contract_check(
    workflow_id: str,
    strict: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    row = _ensure_workflow_access(session, workflow_id, current_user)
    nodespec_map = _nodespec_map(session)
    result = compile_workflow_contract(row.graph or {"nodes": [], "edges": []}, nodespec_map, strict=strict)
    return _to_compile_read(result, strict)


@router.get("/workflows/{workflow_id}/contract-fix-suggestions", response_model=list[ContractFixSuggestionRead])
def get_contract_fix_suggestions(
    workflow_id: str,
    strict: bool = Query(default=False),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    row = _ensure_workflow_access(session, workflow_id, current_user)
    nodespec_map = _nodespec_map(session)
    result = compile_workflow_contract(row.graph or {"nodes": [], "edges": []}, nodespec_map, strict=strict)
    return [ContractFixSuggestionRead(**item) for item in result.get("suggestions", [])]


@router.post("/workflows/{workflow_id}/contract-fix-rollback", response_model=ContractFixRollbackRead)
def rollback_contract_fixes(
    workflow_id: str,
    payload: ContractFixRollbackRequest,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    row = _ensure_workflow_access(session, workflow_id, current_user)
    if payload.revision_id:
        target_revision = session.get(WorkflowGraphRevision, payload.revision_id)
        if not target_revision or target_revision.workflow_id != workflow_id:
            raise HTTPException(status_code=404, detail="revision not found")
    else:
        target_revision = session.exec(
            select(WorkflowGraphRevision)
            .where(
                WorkflowGraphRevision.workflow_id == workflow_id,
                WorkflowGraphRevision.source == "contract_fix_apply",
            )
            .order_by(WorkflowGraphRevision.revision_no.desc())
        ).first()
        if not target_revision:
            raise HTTPException(status_code=404, detail="no contract fix checkpoint found")

    _create_graph_revision(
        session,
        row.id,
        source="contract_fix_rollback",
        graph=row.graph or {"nodes": [], "edges": []},
        meta={"restored_revision_id": target_revision.id},
    )
    row.graph = target_revision.graph or {"nodes": [], "edges": []}
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)

    nodespec_map = _nodespec_map(session)
    compile_after = compile_workflow_contract(row.graph or {"nodes": [], "edges": []}, nodespec_map, strict=False)
    return ContractFixRollbackRead(
        workflow=_workflow_to_read(row),
        compile=_to_compile_read(compile_after, strict=False),
        restored_revision_id=target_revision.id,
        applied_actions=[
            ContractFixAppliedActionRead(
                index=0,
                action="rollback_contract_fix",
                status="applied",
                message="已回滚到自动修复前图版本",
                patch={"restored_revision_id": target_revision.id},
            )
        ],
    )


@router.get("/workflows/{workflow_id}/graph-revisions", response_model=list[GraphRevisionRead])
def list_workflow_graph_revisions(
    workflow_id: str,
    source: str | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=200),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    _ensure_workflow_access(session, workflow_id, current_user)
    query = select(WorkflowGraphRevision).where(WorkflowGraphRevision.workflow_id == workflow_id)
    if source:
        query = query.where(WorkflowGraphRevision.source == source)
    rows = list(session.exec(query.order_by(WorkflowGraphRevision.revision_no.desc())))[:limit]
    return [
        GraphRevisionRead(
            id=item.id,
            workflow_id=item.workflow_id,
            revision_no=item.revision_no,
            source=item.source,
            meta=item.meta or {},
            created_at=item.created_at,
        )
        for item in rows
    ]


@router.put("/workflows/{workflow_id}/observability/slo-config", response_model=SLOTemplateRead)
def update_workflow_slo_config(
    workflow_id: str,
    payload: SLOConfigUpdateRequest,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    row = _ensure_workflow_access(session, workflow_id, current_user)
    if payload.profile and payload.profile not in PROFILE_THRESHOLDS:
        raise HTTPException(status_code=400, detail=f"unsupported profile: {payload.profile}")
    row.slo_profile = payload.profile or None
    row.slo_overrides = {key: float(value) for key, value in payload.overrides.items()}
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)

    template = resolve_slo_profile(row.category, row.tags, preferred_profile=row.slo_profile)
    thresholds = {key: int(value) for key, value in template.get("thresholds", DEFAULT_THRESHOLDS).items()}
    thresholds.update({key: int(value) for key, value in (row.slo_overrides or {}).items()})
    return SLOTemplateRead(
        workflow_id=row.id,
        workflow_category=row.category,
        profile=row.slo_profile or str(template.get("profile", "default")),
        reason="workflow_config" if row.slo_profile or row.slo_overrides else str(template.get("reason", "category_auto")),
        thresholds=thresholds,
    )


@router.post("/workflows/{workflow_id}/draft", response_model=WorkflowRead)
def save_draft(
    workflow_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    row = _ensure_workflow_access(session, workflow_id, current_user)
    row.status = "draft"
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _workflow_to_read(row)


@router.post("/workflows/{workflow_id}/run", response_model=RunRead)
def run_workflow(
    workflow_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    _ensure_workflow_access(session, workflow_id, current_user)
    run = start_run(workflow_id, owner_id=current_user.user_id)
    return _run_to_read(run)


@router.get("/templates", response_model=list[TemplateRead])
def get_templates(
    session: Session = Depends(get_session),
    official: bool | None = Query(default=None),
    keyword: str | None = Query(default=None),
):
    query = select(Template).order_by(Template.updated_at.desc())
    if official is not None:
        query = query.where(Template.official == official)
    rows = list(session.exec(query))
    if keyword:
        key = keyword.lower()
        rows = [row for row in rows if key in row.name.lower() or key in row.description.lower()]
    return [_template_to_read(row) for row in rows]


@router.get("/templates/{template_id}", response_model=TemplateRead)
def get_template(template_id: str, session: Session = Depends(get_session)):
    row = session.get(Template, template_id)
    if not row:
        raise HTTPException(status_code=404, detail="template not found")
    return _template_to_read(row)


@router.get("/templates/{template_id}/versions", response_model=list[TemplateVersionRead])
def list_template_versions(template_id: str, session: Session = Depends(get_session)):
    template = session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="template not found")
    rows = list(
        session.exec(
            select(TemplateVersion).where(TemplateVersion.template_id == template_id).order_by(TemplateVersion.created_at.desc())
        )
    )
    return [_template_version_to_read(item) for item in rows]


@router.post("/templates/{template_id}/versions", response_model=TemplateVersionRead)
def create_template_version(
    template_id: str,
    payload: TemplateVersionCreateRequest,
    session: Session = Depends(get_session),
    _admin: AuthUser = Depends(require_role("admin")),
):
    template = session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="template not found")
    rows = list(session.exec(select(TemplateVersion).where(TemplateVersion.template_id == template_id)))
    existing_versions = [item.version for item in rows]
    next_version = (payload.version or "").strip() or _next_template_version(existing_versions)
    if next_version in existing_versions:
        raise HTTPException(status_code=400, detail=f"template version exists: {next_version}")
    row = TemplateVersion(
        id=f"tv-{uuid.uuid4().hex[:10]}",
        template_id=template_id,
        version=next_version,
        changelog=payload.changelog or "manual snapshot",
        graph=template.graph or {"nodes": [], "edges": []},
        created_at=datetime.utcnow(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _template_version_to_read(row)


@router.post("/templates/{template_id}/versions/rollback", response_model=TemplateVersionRollbackRead)
def rollback_template_version(
    template_id: str,
    payload: TemplateVersionRollbackRequest,
    session: Session = Depends(get_session),
    _admin: AuthUser = Depends(require_role("admin")),
):
    template = session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="template not found")
    target: TemplateVersion | None = None
    if payload.version_id:
        target = session.get(TemplateVersion, payload.version_id)
        if target and target.template_id != template_id:
            target = None
    elif payload.version:
        target = session.exec(
            select(TemplateVersion).where(
                TemplateVersion.template_id == template_id,
                TemplateVersion.version == payload.version,
            )
        ).first()
    else:
        target = session.exec(
            select(TemplateVersion).where(TemplateVersion.template_id == template_id).order_by(TemplateVersion.created_at.desc())
        ).first()
    if not target:
        raise HTTPException(status_code=404, detail="template version not found")

    rows = list(session.exec(select(TemplateVersion).where(TemplateVersion.template_id == template_id)))
    next_version = _next_template_version([item.version for item in rows])
    created = TemplateVersion(
        id=f"tv-{uuid.uuid4().hex[:10]}",
        template_id=template_id,
        version=next_version,
        changelog=payload.changelog or f"rollback to {target.version}",
        graph=target.graph or {"nodes": [], "edges": []},
        created_at=datetime.utcnow(),
    )
    template.graph = target.graph or {"nodes": [], "edges": []}
    template.updated_at = datetime.utcnow()
    session.add(template)
    session.add(created)
    session.commit()
    session.refresh(template)
    session.refresh(created)
    return TemplateVersionRollbackRead(
        template=_template_to_read(template),
        restored_version=_template_version_to_read(target),
        created_version=_template_version_to_read(created),
    )


@router.get("/templates/{template_id}/versions/diff", response_model=TemplateVersionDiffRead)
def get_template_version_diff(
    template_id: str,
    from_version: str = Query(..., description="起始版本号"),
    to_version: str = Query(..., description="目标版本号"),
    session: Session = Depends(get_session),
):
    template = session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="template not found")
    from_row = session.exec(
        select(TemplateVersion).where(
            TemplateVersion.template_id == template_id,
            TemplateVersion.version == from_version,
        )
    ).first()
    to_row = session.exec(
        select(TemplateVersion).where(
            TemplateVersion.template_id == template_id,
            TemplateVersion.version == to_version,
        )
    ).first()
    if not from_row or not to_row:
        raise HTTPException(status_code=404, detail="template version not found")
    diff = _graph_version_diff(from_row.graph or {}, to_row.graph or {})
    diff.template_id = template_id
    diff.from_version = from_version
    diff.to_version = to_version
    return diff


@router.post("/templates/{template_id}/clone", response_model=WorkflowRead)
def clone_template(
    template_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    template = session.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="template not found")
    workflow = Workflow(
        id=f"wf-{uuid.uuid4().hex[:8]}",
        name=f"{template.name}-副本",
        category=template.category,
        tags=template.tags,
        status="draft",
        updated_at=datetime.utcnow(),
        owner_id=current_user.user_id,
        description=template.description,
        source_template_id=template.id,
        graph=template.graph,
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return _workflow_to_read(workflow)


@router.get("/runs", response_model=list[RunRead])
def get_runs(
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    rows = list_runs(session)
    if not _is_admin(current_user):
        rows = [row for row in rows if _can_access_owner(row.owner_id, current_user)]
    return [_run_to_read(row) for row in rows]


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(
    run_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    row = _ensure_run_access(session, run_id, current_user)
    return _run_to_read(row)


@router.post("/runs/{run_id}/cancel", response_model=RunRead)
def cancel_run_api(
    run_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    _ensure_run_access(session, run_id, current_user)
    result = cancel_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="run not found")
    return _run_to_read(result)


@router.post("/runs/{run_id}/retry", response_model=RunRead)
def retry_run_api(
    run_id: str,
    payload: RunRetryRequest | None = None,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    _ensure_run_access(session, run_id, current_user)
    retry_payload = payload or RunRetryRequest()
    try:
        new_run = retry_run(
            run_id,
            owner_id=current_user.user_id,
            strategy=retry_payload.strategy,
            max_attempts=retry_payload.max_attempts,
            backoff_sec=retry_payload.backoff_sec,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _run_to_read(new_run)


@router.get("/runs/{run_id}/logs", response_model=list[RunLogRead])
def get_run_logs(
    run_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    _ensure_run_access(session, run_id, current_user)
    rows = list_run_logs(session, run_id)
    return [
        RunLogRead(
            id=row.id,
            run_id=row.run_id,
            workflow_id=row.workflow_id,
            level=row.level,
            node_id=row.node_id,
            node_name=row.node_name,
            error_code=row.error_code,
            detail=row.detail or {},
            message=row.message,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/runs/{run_id}/node-states", response_model=list[NodeStateRead])
def get_run_node_states(
    run_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    _ensure_run_access(session, run_id, current_user)
    rows = list_node_states(session, run_id)
    return [
        NodeStateRead(
            id=row.id,
            run_id=row.run_id,
            workflow_id=row.workflow_id,
            node_id=row.node_id,
            node_name=row.node_name,
            status=row.status,
            started_at=row.started_at,
            finished_at=row.finished_at,
            duration_ms=row.duration_ms,
            error_code=row.error_code,
            message=row.message,
        )
        for row in rows
    ]


@router.get("/runs/{run_id}/observability", response_model=RunObservabilityRead)
def get_run_metrics(
    run_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    run = _ensure_run_access(session, run_id, current_user)
    return RunObservabilityRead(
        run_id=run.id,
        workflow_id=run.workflow_id,
        summary=get_run_observability(session, run.id),
    )


@router.get("/runs/{run_id}/observability/alerts", response_model=RunAlertsRead)
def get_run_metric_alerts(
    run_id: str,
    use_template: bool = Query(default=True),
    profile: str | None = Query(default=None),
    p95_node_duration_ms: int | None = Query(default=None),
    failed_nodes: int | None = Query(default=None),
    warn_logs: int | None = Query(default=None),
    error_logs: int | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    run = _ensure_run_access(session, run_id, current_user)
    workflow = session.get(Workflow, run.workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="workflow not found")
    thresholds = _resolve_slo_thresholds(
        workflow,
        use_template=use_template,
        profile=profile,
        overrides={
            "p95_node_duration_ms": p95_node_duration_ms,
            "failed_nodes": failed_nodes,
            "warn_logs": warn_logs,
            "error_logs": error_logs,
        },
    )
    alerts = get_run_alerts(session, run.id, thresholds=thresholds)
    return RunAlertsRead(run_id=run.id, workflow_id=run.workflow_id, alerts=alerts, thresholds=thresholds)


@router.get("/runs/{run_id}/observability/series", response_model=list[RunMetricPointRead])
def get_run_metric_series(
    run_id: str,
    metric_name: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    _ensure_run_access(session, run_id, current_user)
    rows = list_run_metric_points(session, run_id, metric_name=metric_name, limit=limit)
    return [
        RunMetricPointRead(
            id=row.id,
            run_id=row.run_id,
            workflow_id=row.workflow_id,
            metric_name=row.metric_name,
            value=row.value,
            tags=row.tags or {},
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/workflows/{workflow_id}/observability/series", response_model=list[RunMetricPointRead])
def get_workflow_metric_series(
    workflow_id: str,
    metric_name: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    _ensure_workflow_access(session, workflow_id, current_user)
    rows = list_workflow_metric_points(session, workflow_id, metric_name=metric_name, limit=limit)
    return [
        RunMetricPointRead(
            id=row.id,
            run_id=row.run_id,
            workflow_id=row.workflow_id,
            metric_name=row.metric_name,
            value=row.value,
            tags=row.tags or {},
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/workflows/{workflow_id}/observability/compare", response_model=RunCompareRead)
def compare_workflow_runs(
    workflow_id: str,
    run_ids: str | None = Query(default=None, description="逗号分隔 run_id 列表；为空则自动取最近 5 次"),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    _ensure_workflow_access(session, workflow_id, current_user)
    selected_ids = [item.strip() for item in (run_ids or "").split(",") if item.strip()]
    if selected_ids:
        runs = [session.get(Run, item) for item in selected_ids]
        rows = [item for item in runs if item and item.workflow_id == workflow_id]
    else:
        rows = list(
            session.exec(select(Run).where(Run.workflow_id == workflow_id).order_by(Run.created_at.desc()))
        )[:5]
    rows = sorted(rows, key=lambda item: item.created_at)

    metrics: dict[str, dict[str, float | int | str | None]] = {}
    for row in rows:
        summary = row.observability or {}
        metrics[row.id] = {
            "status": row.status,
            "created_at": row.created_at.isoformat(),
            "total_nodes": int(summary.get("total_nodes", 0)),
            "failed_nodes": int(summary.get("failed_nodes", 0)),
            "warn_logs": int(summary.get("warn_logs", 0)),
            "error_logs": int(summary.get("error_logs", 0)),
            "avg_node_duration_ms": int(summary.get("avg_node_duration_ms", 0)),
            "p95_node_duration_ms": int(summary.get("p95_node_duration_ms", 0)),
            "total_duration_ms": int(summary.get("total_duration_ms", 0)),
        }

    return RunCompareRead(workflow_id=workflow_id, run_ids=[item.id for item in rows], metrics=metrics)


@router.get("/workflows/{workflow_id}/observability/trends", response_model=WorkflowTrendRead)
def get_workflow_observability_trends(
    workflow_id: str,
    metrics: str | None = Query(default=None, description="逗号分隔指标名"),
    window_size: int = Query(default=30, ge=1, le=300),
    use_template: bool = Query(default=True),
    profile: str | None = Query(default=None),
    p95_node_duration_ms: int | None = Query(default=None, ge=1),
    failed_nodes: int | None = Query(default=None, ge=0),
    warn_logs: int | None = Query(default=None, ge=0),
    error_logs: int | None = Query(default=None, ge=0),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    workflow = _ensure_workflow_access(session, workflow_id, current_user)

    default_metrics = [
        "p95_node_duration_ms",
        "failed_nodes",
        "warn_logs",
        "error_logs",
        "total_duration_ms",
    ]
    selected_metrics = [item.strip() for item in (metrics or "").split(",") if item.strip()] or default_metrics
    rows = list(
        session.exec(select(Run).where(Run.workflow_id == workflow_id).order_by(Run.created_at.desc()))
    )[:window_size]
    rows = sorted(rows, key=lambda item: item.created_at)
    thresholds = _resolve_slo_thresholds(
        workflow,
        use_template=use_template,
        profile=profile,
        overrides={
            "p95_node_duration_ms": p95_node_duration_ms,
            "failed_nodes": failed_nodes,
            "warn_logs": warn_logs,
            "error_logs": error_logs,
        },
    )

    points: dict[str, list[TrendPointRead]] = {}
    for metric_name in selected_metrics:
        metric_points: list[TrendPointRead] = []
        for row in rows:
            summary = row.observability or {}
            raw_value = summary.get(metric_name, 0)
            try:
                value = float(raw_value or 0)
            except (TypeError, ValueError):
                value = 0.0
            threshold = float(thresholds.get(metric_name)) if metric_name in thresholds else None
            metric_points.append(
                TrendPointRead(
                    run_id=row.id,
                    created_at=row.created_at.isoformat(),
                    status=row.status,
                    value=value,
                    threshold=threshold,
                )
            )
        points[metric_name] = metric_points

    return WorkflowTrendRead(
        workflow_id=workflow_id,
        metrics=selected_metrics,
        run_ids=[item.id for item in rows],
        thresholds=thresholds,
        points=points,
    )


@router.get("/workflows/{workflow_id}/observability/alerts", response_model=WorkflowAlertsRead)
def get_workflow_alert_incidents(
    workflow_id: str,
    window_size: int = Query(default=30, ge=1, le=300),
    use_template: bool = Query(default=True),
    profile: str | None = Query(default=None),
    p95_node_duration_ms: int | None = Query(default=None, ge=1),
    failed_nodes: int | None = Query(default=None, ge=0),
    warn_logs: int | None = Query(default=None, ge=0),
    error_logs: int | None = Query(default=None, ge=0),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    workflow = _ensure_workflow_access(session, workflow_id, current_user)
    thresholds = _resolve_slo_thresholds(
        workflow,
        use_template=use_template,
        profile=profile,
        overrides={
            "p95_node_duration_ms": p95_node_duration_ms,
            "failed_nodes": failed_nodes,
            "warn_logs": warn_logs,
            "error_logs": error_logs,
        },
    )
    rows = list(
        session.exec(select(Run).where(Run.workflow_id == workflow_id).order_by(Run.created_at.desc()))
    )[:window_size]
    counts: dict[str, int] = {}
    incidents: list[AlertIncidentRead] = []
    for row in rows:
        alerts = get_run_alerts(session, row.id, thresholds=thresholds)
        if not alerts:
            continue
        for item in alerts:
            code = str(item.get("code") or "unknown")
            counts[code] = counts.get(code, 0) + 1
        incidents.append(
            AlertIncidentRead(
                run_id=row.id,
                created_at=row.created_at.isoformat(),
                status=row.status,
                alerts=alerts,
            )
        )
    return WorkflowAlertsRead(
        workflow_id=workflow_id,
        window_size=window_size,
        thresholds=thresholds,
        total_runs=len(rows),
        alert_runs=len(incidents),
        counts=counts,
        incidents=incidents,
    )


@router.get("/workflows/{workflow_id}/observability/insights", response_model=WorkflowInsightsRead)
def get_workflow_observability_insights(
    workflow_id: str,
    window_size: int = Query(default=30, ge=1, le=300),
    use_template: bool = Query(default=True),
    profile: str | None = Query(default=None),
    p95_node_duration_ms: int | None = Query(default=None, ge=1),
    failed_nodes: int | None = Query(default=None, ge=0),
    warn_logs: int | None = Query(default=None, ge=0),
    error_logs: int | None = Query(default=None, ge=0),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    workflow = _ensure_workflow_access(session, workflow_id, current_user)
    thresholds = _resolve_slo_thresholds(
        workflow,
        use_template=use_template,
        profile=profile,
        overrides={
            "p95_node_duration_ms": p95_node_duration_ms,
            "failed_nodes": failed_nodes,
            "warn_logs": warn_logs,
            "error_logs": error_logs,
        },
    )
    rows = list(
        session.exec(select(Run).where(Run.workflow_id == workflow_id).order_by(Run.created_at.desc()))
    )[:window_size]
    total_runs = len(rows)
    if total_runs == 0:
        return WorkflowInsightsRead(
            workflow_id=workflow_id,
            window_size=window_size,
            health_score=100,
            health_level="healthy",
            pass_rate=1.0,
            alert_runs=0,
            total_runs=0,
            latest_run_id=None,
            latest_summary={},
            thresholds=thresholds,
            suggested_slo_config={},
            recommendations=[
                ObservabilityRecommendationRead(
                    code="R_EMPTY",
                    level="info",
                    message="暂无运行样本，建议先运行工作流生成观测数据。",
                    action="执行至少 3 次运行后再观察趋势与告警。",
                )
            ],
        )

    pass_count = 0
    alert_runs = 0
    for row in rows:
        summary = row.observability or {}
        p95 = int(summary.get("p95_node_duration_ms", 0) or 0)
        failed = int(summary.get("failed_nodes", 0) or 0)
        warns = int(summary.get("warn_logs", 0) or 0)
        errors = int(summary.get("error_logs", 0) or 0)
        passed = (
            p95 <= int(thresholds.get("p95_node_duration_ms", 0))
            and failed <= int(thresholds.get("failed_nodes", 0))
            and warns <= int(thresholds.get("warn_logs", 0))
            and errors <= int(thresholds.get("error_logs", 0))
            and row.status == "success"
        )
        if passed:
            pass_count += 1
        if get_run_alerts(session, row.id, thresholds=thresholds):
            alert_runs += 1

    pass_rate = pass_count / total_runs
    latest = rows[0]
    latest_raw = latest.observability or {}
    latest_summary = {
        "status": latest.status,
        "created_at": latest.created_at.isoformat(),
        "p95_node_duration_ms": int(latest_raw.get("p95_node_duration_ms", 0) or 0),
        "failed_nodes": int(latest_raw.get("failed_nodes", 0) or 0),
        "warn_logs": int(latest_raw.get("warn_logs", 0) or 0),
        "error_logs": int(latest_raw.get("error_logs", 0) or 0),
        "total_duration_ms": int(latest_raw.get("total_duration_ms", 0) or 0),
    }
    p95_ratio = 0.0
    threshold_p95 = max(1, int(thresholds.get("p95_node_duration_ms", 1)))
    if latest_summary["p95_node_duration_ms"] > threshold_p95:
        p95_ratio = (float(latest_summary["p95_node_duration_ms"]) / threshold_p95) - 1.0
    health_score = 100
    health_score -= int((1.0 - pass_rate) * 40)
    health_score -= min(20, int(p95_ratio * 20))
    health_score -= min(20, int(latest_summary["failed_nodes"]) * 10)
    health_score -= min(20, int(latest_summary["error_logs"]) * 10 + int(latest_summary["warn_logs"]) // 5)
    health_score = max(0, min(100, health_score))
    if health_score >= 85:
        health_level = "healthy"
    elif health_score >= 60:
        health_level = "warning"
    else:
        health_level = "critical"

    recommendations = _build_insight_recommendations(
        pass_rate=pass_rate,
        latest_summary=latest_summary,
        thresholds={key: int(value) for key, value in thresholds.items()},
        alert_runs=alert_runs,
    )
    suggested_slo_config = _build_suggested_slo_config(
        pass_rate=pass_rate,
        latest_summary=latest_summary,
        thresholds={key: int(value) for key, value in thresholds.items()},
    )
    return WorkflowInsightsRead(
        workflow_id=workflow_id,
        window_size=window_size,
        health_score=health_score,
        health_level=health_level,
        pass_rate=pass_rate,
        alert_runs=alert_runs,
        total_runs=total_runs,
        latest_run_id=latest.id,
        latest_summary=latest_summary,
        thresholds=thresholds,
        suggested_slo_config=suggested_slo_config,
        recommendations=[ObservabilityRecommendationRead(**item) for item in recommendations],
    )


@router.get("/workflows/{workflow_id}/observability/anomalies", response_model=WorkflowAnomaliesRead)
def get_workflow_observability_anomalies(
    workflow_id: str,
    metrics: str | None = Query(default=None, description="逗号分隔指标名"),
    window_size: int = Query(default=30, ge=1, le=300),
    z_threshold: float = Query(default=3.0, ge=1.0, le=10.0),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    _ensure_workflow_access(session, workflow_id, current_user)

    default_metrics = [
        "p95_node_duration_ms",
        "failed_nodes",
        "warn_logs",
        "error_logs",
        "total_duration_ms",
    ]
    selected_metrics = [item.strip() for item in (metrics or "").split(",") if item.strip()] or default_metrics
    rows = list(
        session.exec(select(Run).where(Run.workflow_id == workflow_id).order_by(Run.created_at.desc()))
    )[:window_size]

    anomaly_by_metric: dict[str, int] = {metric_name: 0 for metric_name in selected_metrics}
    anomalies: list[ObservabilityAnomalyRead] = []
    for metric_name in selected_metrics:
        metric_values: list[float] = []
        valid_rows: list[Run] = []
        for row in rows:
            raw = (row.observability or {}).get(metric_name)
            try:
                value = float(raw or 0)
            except (TypeError, ValueError):
                continue
            metric_values.append(value)
            valid_rows.append(row)
        if not metric_values:
            continue
        baseline, _, z_scores = _robust_z_scores(metric_values)
        for row, value, z_score in zip(valid_rows, metric_values, z_scores):
            if abs(z_score) < z_threshold:
                continue
            if abs(value - baseline) < 1e-12:
                continue
            level = "critical" if abs(z_score) >= (z_threshold * 1.5) else "warning"
            anomaly_by_metric[metric_name] = anomaly_by_metric.get(metric_name, 0) + 1
            direction = "高于" if value > baseline else "低于"
            anomalies.append(
                ObservabilityAnomalyRead(
                    run_id=row.id,
                    metric_name=metric_name,
                    value=value,
                    baseline=baseline,
                    z_score=z_score,
                    level=level,
                    status=row.status,
                    created_at=row.created_at.isoformat(),
                    message=(
                        f"{metric_name} 异常，当前值 {value:.2f}，较基线 {baseline:.2f} {direction}"
                        f"（z={z_score:.2f}）"
                    ),
                )
            )

    anomalies = sorted(anomalies, key=lambda item: abs(item.z_score), reverse=True)
    return WorkflowAnomaliesRead(
        workflow_id=workflow_id,
        window_size=window_size,
        z_threshold=z_threshold,
        metrics=selected_metrics,
        total_runs=len(rows),
        anomaly_count=len(anomalies),
        anomaly_by_metric=anomaly_by_metric,
        anomalies=anomalies[:100],
    )


@router.get("/workflows/{workflow_id}/observability/insights-report", response_model=ObservabilityReportRead)
def get_workflow_observability_report(
    workflow_id: str,
    window_size: int = Query(default=30, ge=1, le=300),
    use_template: bool = Query(default=True),
    z_threshold: float = Query(default=2.8, ge=1.0, le=10.0),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    workflow = _ensure_workflow_access(session, workflow_id, current_user)

    slo_view = get_workflow_slo_view(
        workflow_id=workflow_id,
        window_size=window_size,
        use_template=use_template,
        profile=None,
        p95_node_duration_ms=None,
        failed_nodes=None,
        warn_logs=None,
        error_logs=None,
        session=session,
    )
    alerts_view = get_workflow_alert_incidents(
        workflow_id=workflow_id,
        window_size=window_size,
        use_template=use_template,
        profile=None,
        p95_node_duration_ms=None,
        failed_nodes=None,
        warn_logs=None,
        error_logs=None,
        session=session,
    )
    insights_view = get_workflow_observability_insights(
        workflow_id=workflow_id,
        window_size=window_size,
        use_template=use_template,
        profile=None,
        p95_node_duration_ms=None,
        failed_nodes=None,
        warn_logs=None,
        error_logs=None,
        session=session,
    )
    anomaly_view = get_workflow_observability_anomalies(
        workflow_id=workflow_id,
        metrics=None,
        window_size=window_size,
        z_threshold=z_threshold,
        session=session,
    )

    lines = [
        f"# 可观测性洞察报告 · {workflow.name}",
        "",
        f"- 工作流 ID：`{workflow_id}`",
        f"- 时间窗口：最近 `{window_size}` 次运行",
        f"- 生成时间：`{datetime.utcnow().isoformat()}`",
        "",
        "## 1) 健康度总览",
        f"- 健康分：**{insights_view.health_score}**（{insights_view.health_level}）",
        f"- SLO 通过率：**{insights_view.pass_rate * 100:.1f}%**（{insights_view.total_runs} runs）",
        f"- 告警运行数：**{insights_view.alert_runs}**",
        "",
        "## 2) 阈值配置",
        f"- p95_node_duration_ms: `{slo_view.thresholds.get('p95_node_duration_ms', 0)}`",
        f"- failed_nodes: `{slo_view.thresholds.get('failed_nodes', 0)}`",
        f"- warn_logs: `{slo_view.thresholds.get('warn_logs', 0)}`",
        f"- error_logs: `{slo_view.thresholds.get('error_logs', 0)}`",
        "",
        "## 3) 告警分布",
    ]
    if alerts_view.counts:
        for code, count in sorted(alerts_view.counts.items(), key=lambda item: item[1], reverse=True):
            lines.append(f"- {code}: {count}")
    else:
        lines.append("- 最近窗口无告警事件")

    lines.extend(["", "## 4) 异常检测（鲁棒 Z-Score）"])
    if anomaly_view.anomalies:
        lines.append(f"- 检测到异常点：**{anomaly_view.anomaly_count}**（阈值 z={anomaly_view.z_threshold}）")
        for row in anomaly_view.anomalies[:8]:
            lines.append(
                f"- `{row.metric_name}` · run `{row.run_id}` · 值 {row.value:.2f} / 基线 {row.baseline:.2f} · z={row.z_score:.2f} · {row.level}"
            )
    else:
        lines.append("- 当前窗口未检测到异常点")

    lines.extend(["", "## 5) 自动建议"])
    if insights_view.recommendations:
        for rec in insights_view.recommendations[:8]:
            lines.append(f"- [{rec.level.upper()}] `{rec.code}`：{rec.message}；建议：{rec.action}")
    else:
        lines.append("- 暂无建议")

    lines.extend(["", "## 6) 推荐 SLO 调整"])
    suggested = insights_view.suggested_slo_config or {}
    if suggested:
        lines.append(f"- profile: `{suggested.get('profile')}`")
        overrides = suggested.get("overrides", {})
        if overrides:
            for key, value in overrides.items():
                lines.append(f"  - {key}: `{value}`")
        reason = suggested.get("reason")
        if reason:
            lines.append(f"- reason: {reason}")
    else:
        lines.append("- 无推荐调整")

    return ObservabilityReportRead(
        workflow_id=workflow_id,
        window_size=window_size,
        generated_at=datetime.utcnow().isoformat(),
        markdown="\n".join(lines),
    )


@router.get("/workflows/{workflow_id}/observability/slo", response_model=SLOViewRead)
def get_workflow_slo_view(
    workflow_id: str,
    window_size: int = Query(default=20, ge=1, le=200),
    use_template: bool = Query(default=True),
    profile: str | None = Query(default=None),
    p95_node_duration_ms: int | None = Query(default=None, ge=1),
    failed_nodes: int | None = Query(default=None, ge=0),
    warn_logs: int | None = Query(default=None, ge=0),
    error_logs: int | None = Query(default=None, ge=0),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    workflow = _ensure_workflow_access(session, workflow_id, current_user)
    rows = list(
        session.exec(select(Run).where(Run.workflow_id == workflow_id).order_by(Run.created_at.desc()))
    )[:window_size]
    rows = sorted(rows, key=lambda item: item.created_at)
    thresholds = _resolve_slo_thresholds(
        workflow,
        use_template=use_template,
        profile=profile,
        overrides={
            "p95_node_duration_ms": p95_node_duration_ms,
            "failed_nodes": failed_nodes,
            "warn_logs": warn_logs,
            "error_logs": error_logs,
        },
    )
    run_views: list[dict[str, Any]] = []
    pass_count = 0
    for row in rows:
        summary = row.observability or {}
        p95 = int(summary.get("p95_node_duration_ms", 0))
        failed = int(summary.get("failed_nodes", 0))
        warns = int(summary.get("warn_logs", 0))
        errors = int(summary.get("error_logs", 0))
        ok = (
            p95 <= int(thresholds["p95_node_duration_ms"])
            and failed <= int(thresholds["failed_nodes"])
            and warns <= int(thresholds["warn_logs"])
            and errors <= int(thresholds["error_logs"])
            and row.status == "success"
        )
        if ok:
            pass_count += 1
        run_views.append(
            {
                "run_id": row.id,
                "status": row.status,
                "created_at": row.created_at.isoformat(),
                "p95_node_duration_ms": p95,
                "failed_nodes": failed,
                "warn_logs": warns,
                "error_logs": errors,
                "slo_pass": ok,
            }
        )
    total = len(run_views)
    fail_count = total - pass_count
    pass_rate = (pass_count / total) if total else 0.0
    return SLOViewRead(
        workflow_id=workflow_id,
        window_size=window_size,
        thresholds=thresholds,
        pass_rate=pass_rate,
        pass_count=pass_count,
        fail_count=fail_count,
        runs=run_views,
    )


@router.get("/workflows/{workflow_id}/observability/slo-template", response_model=SLOTemplateRead)
def get_workflow_slo_template(
    workflow_id: str,
    profile: str | None = Query(default=None),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    workflow = _ensure_workflow_access(session, workflow_id, current_user)
    preferred_profile = profile or workflow.slo_profile
    result = resolve_slo_profile(workflow.category, workflow.tags, preferred_profile=preferred_profile)
    thresholds = {key: int(value) for key, value in result.get("thresholds", DEFAULT_THRESHOLDS).items()}
    thresholds.update({key: int(value) for key, value in (workflow.slo_overrides or {}).items()})
    return SLOTemplateRead(
        workflow_id=workflow.id,
        workflow_category=workflow.category,
        profile=str(preferred_profile or result.get("profile", "default")),
        reason="workflow_config" if workflow.slo_profile or workflow.slo_overrides else str(result.get("reason", "category_auto")),
        thresholds=thresholds,
    )


@router.get("/reports/{workflow_id}", response_model=ReportRead | None)
def get_report(
    workflow_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    _ensure_workflow_access(session, workflow_id, current_user)
    row = session.get(Report, workflow_id)
    if not row:
        return None
    return ReportRead(
        workflow_id=row.workflow_id,
        workflow_name=row.workflow_name,
        metrics=row.metrics,
        equity_series=row.equity_series,
        layer_return=row.layer_return,
        updated_at=row.updated_at,
    )


@router.post("/artifacts/upload", response_model=ArtifactRead)
async def upload_artifact(
    file: UploadFile = File(...),
    kind: str = Form(default="generic"),
    logical_key: str = Form(default="default"),
    parent_artifact_id: str | None = Form(default=None),
    activate: bool = Form(default=True),
    workflow_id: str | None = Form(default=None),
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="invalid filename")
    suffix = Path(file.filename).suffix
    artifact_id = f"art-{uuid.uuid4().hex[:10]}"
    save_path = Path(settings.artifact_dir) / f"{artifact_id}{suffix}"
    content = await file.read()
    save_path.write_bytes(content)
    sha256 = hashlib.sha256(content).hexdigest()
    lk = (logical_key or "default").strip() or "default"
    if workflow_id is not None:
        _ensure_workflow_access(session, workflow_id, current_user)

    version_query = select(UploadedArtifact).where(
        UploadedArtifact.kind == kind,
        UploadedArtifact.logical_key == lk,
    )
    if workflow_id is None:
        version_query = version_query.where(UploadedArtifact.workflow_id.is_(None))
    else:
        version_query = version_query.where(UploadedArtifact.workflow_id == workflow_id)
    siblings = list(session.exec(version_query.order_by(UploadedArtifact.version.desc())))
    next_version = (siblings[0].version + 1) if siblings else 1

    row = UploadedArtifact(
        id=artifact_id,
        workflow_id=workflow_id,
        kind=kind,
        logical_key=lk,
        version=next_version,
        is_active=activate,
        parent_artifact_id=parent_artifact_id,
        file_name=file.filename,
        file_size=len(content),
        content_type=file.content_type,
        sha256=sha256,
        audit={
            "event": "upload",
            "logical_key": lk,
            "version": next_version,
            "parent_artifact_id": parent_artifact_id,
            "uploaded_at": datetime.utcnow().isoformat(),
        },
        file_path=str(save_path),
        created_at=datetime.utcnow(),
    )
    if activate:
        for item in siblings:
            if item.is_active:
                item.is_active = False
                session.add(item)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _artifact_to_read(row)


@router.get("/artifacts", response_model=list[ArtifactRead])
def list_artifacts(
    session: Session = Depends(get_session),
    workflow_id: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    logical_key: str | None = Query(default=None),
    active_only: bool = Query(default=False),
    current_user: AuthUser = Depends(require_request_access),
):
    query = select(UploadedArtifact).order_by(
        UploadedArtifact.logical_key.asc(),
        UploadedArtifact.version.desc(),
        UploadedArtifact.created_at.desc(),
    )
    if workflow_id:
        query = query.where(UploadedArtifact.workflow_id == workflow_id)
    if kind:
        query = query.where(UploadedArtifact.kind == kind)
    if logical_key:
        query = query.where(UploadedArtifact.logical_key == logical_key)
    if active_only:
        query = query.where(UploadedArtifact.is_active.is_(True))
    rows = list(session.exec(query))
    if not _is_admin(current_user):
        rows = [row for row in rows if _can_access_owner(row.workflow_id, current_user)]
    return [_artifact_to_read(row) for row in rows]


@router.get("/artifacts/{artifact_id}", response_model=ArtifactRead)
def get_artifact(
    artifact_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    row = session.get(UploadedArtifact, artifact_id)
    if not row:
        raise HTTPException(status_code=404, detail="artifact not found")
    if not _can_access_owner(row.workflow_id, current_user):
        raise HTTPException(status_code=403, detail="forbidden: artifact access denied")
    return _artifact_to_read(row)


@router.post("/artifacts/{artifact_id}/rollback", response_model=ArtifactRead)
def rollback_artifact(
    artifact_id: str,
    payload: ArtifactRollbackRequest,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    target = session.get(UploadedArtifact, artifact_id)
    if not target:
        raise HTTPException(status_code=404, detail="artifact not found")
    if not _can_access_owner(target.workflow_id, current_user):
        raise HTTPException(status_code=403, detail="forbidden: artifact access denied")

    query = select(UploadedArtifact).where(
        UploadedArtifact.kind == target.kind,
        UploadedArtifact.logical_key == target.logical_key,
    )
    if target.workflow_id is None:
        query = query.where(UploadedArtifact.workflow_id.is_(None))
    else:
        query = query.where(UploadedArtifact.workflow_id == target.workflow_id)
    siblings = list(session.exec(query))
    next_version = (max((item.version for item in siblings), default=0) + 1)
    for item in siblings:
        if item.is_active:
            item.is_active = False
            session.add(item)

    new_row = UploadedArtifact(
        id=f"art-{uuid.uuid4().hex[:10]}",
        workflow_id=target.workflow_id,
        kind=target.kind,
        logical_key=target.logical_key,
        version=next_version,
        is_active=True,
        parent_artifact_id=target.id,
        file_name=target.file_name,
        file_size=target.file_size,
        content_type=target.content_type,
        sha256=target.sha256,
        audit={
            "event": "rollback",
            "reason": payload.reason,
            "source_artifact_id": target.id,
            "source_version": target.version,
            "rollback_at": datetime.utcnow().isoformat(),
        },
        file_path=target.file_path,
        created_at=datetime.utcnow(),
    )
    session.add(new_row)
    session.commit()
    session.refresh(new_row)
    return _artifact_to_read(new_row)


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(
    artifact_id: str,
    session: Session = Depends(get_session),
    current_user: AuthUser = Depends(require_request_access),
):
    row = session.get(UploadedArtifact, artifact_id)
    if not row:
        raise HTTPException(status_code=404, detail="artifact not found")
    if not _can_access_owner(row.workflow_id, current_user):
        raise HTTPException(status_code=403, detail="forbidden: artifact access denied")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact file missing")
    return FileResponse(path, filename=row.file_name)
