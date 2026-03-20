from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
import re
from threading import Lock
import time
import uuid

import networkx as nx
import numpy as np
from sqlmodel import Session, select

from ..db import engine
from ..models import NodeSpec, Report, Run, RunLog, RunMetricPoint, UploadedArtifact, Workflow, WorkflowNodeState
from .contract import (
    ERROR_COMPILE_CYCLE,
    compile_workflow_contract,
)
from .node_handlers import RunContext, execute_node, handle_backtest


executor = ThreadPoolExecutor(max_workers=4)
_future_lock = Lock()
_run_futures: dict[str, Future] = {}

ERROR_GRAPH_CYCLE = "E_GRAPH_CYCLE"
ERROR_NODE_EXECUTION = "E_NODE_EXECUTION"
ERROR_RUN_INTERNAL = "E_RUN_INTERNAL"
ERROR_RUN_NOT_FOUND = "E_RUN_NOT_FOUND"
ERROR_RUN_CANCELLED = "E_RUN_CANCELLED"

WARN_ARTIFACT_RESOLVE = "W_ARTIFACT_RESOLVE"
DEFAULT_ALERT_THRESHOLDS = {
    "p95_node_duration_ms": 800,
    "failed_nodes": 1,
    "warn_logs": 20,
    "error_logs": 1,
}


def _fmt_duration(start: float, end: float) -> str:
    seconds = max(1, int(end - start))
    return f"{seconds // 60:02d}m {seconds % 60:02d}s"


def _parse_error(exc: Exception, default_code: str = ERROR_RUN_INTERNAL) -> tuple[str, str]:
    text = str(exc).strip()
    match = re.match(r"^(E_[A-Z0-9_]+)\s*:\s*(.+)$", text)
    if match:
        return match.group(1), match.group(2)
    return default_code, text or "unknown error"


def _append_run_log(
    run_id: str,
    workflow_id: str,
    *,
    level: str,
    message: str,
    node_id: str | None = None,
    node_name: str | None = None,
    error_code: str | None = None,
    detail: dict | None = None,
) -> None:
    with Session(engine) as session:
        session.add(
            RunLog(
                id=f"log-{uuid.uuid4().hex[:10]}",
                run_id=run_id,
                workflow_id=workflow_id,
                level=level,
                node_id=node_id,
                node_name=node_name,
                error_code=error_code,
                detail=detail or {},
                message=message,
                created_at=datetime.utcnow(),
            )
        )
        run = session.get(Run, run_id)
        if run:
            lines = list(run.logs or [])
            prefix = f"[{level}]"
            if error_code:
                prefix += f"[{error_code}]"
            lines.append(f"{prefix} {message}")
            run.logs = lines[-300:]
            run.updated_at = datetime.utcnow()
            session.add(run)
        session.commit()


def _update_run(
    run_id: str,
    *,
    status: str,
    message: str,
    duration: str | None = None,
    observability: dict | None = None,
) -> None:
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if not run:
            return
        run.status = status
        run.message = message
        run.updated_at = datetime.utcnow()
        if duration is not None:
            run.duration = duration
        if observability is not None:
            run.observability = observability
        session.add(run)
        session.commit()


def _record_metric_point(
    run_id: str,
    workflow_id: str,
    metric_name: str,
    value: float,
    tags: dict | None = None,
    *,
    created_at: datetime | None = None,
) -> None:
    with Session(engine) as session:
        session.add(
            RunMetricPoint(
                id=f"mp-{uuid.uuid4().hex[:10]}",
                run_id=run_id,
                workflow_id=workflow_id,
                metric_name=metric_name,
                value=float(value),
                tags=tags or {},
                created_at=created_at or datetime.utcnow(),
            )
        )
        session.commit()


def _track_future(run_id: str, future: Future) -> None:
    with _future_lock:
        _run_futures[run_id] = future

    def _cleanup(_future: Future) -> None:
        with _future_lock:
            _run_futures.pop(run_id, None)

    future.add_done_callback(_cleanup)


def _try_cancel_future(run_id: str) -> bool:
    with _future_lock:
        future = _run_futures.get(run_id)
    if future is None:
        return False
    return bool(future.cancel())


def _is_cancel_requested(run_id: str) -> bool:
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if not run:
            return False
        if run.status == "cancelled":
            return True
        return bool(run.cancel_requested)


def _schedule_retry_after_failure(run_id: str, workflow_id: str, *, error_code: str) -> bool:
    if error_code == ERROR_RUN_CANCELLED:
        return False
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if not run:
            return False
        max_attempts = max(1, int(run.retry_max_attempts or 1))
        current_attempt = max(1, int(run.retry_attempt or 1))
        if current_attempt >= max_attempts:
            return False
        next_attempt = current_attempt + 1
        backoff_sec = max(0, int(run.retry_backoff_sec or 0))
        strategy = str(run.retry_strategy or "immediate")
        if strategy not in {"immediate", "fixed_backoff"}:
            strategy = "immediate"
        owner_id = run.owner_id
        retry_origin = run.retry_origin_run_id or run.retried_from_run_id or run.id

    _append_run_log(
        run_id,
        workflow_id,
        level="WARN",
        message=(
            f"触发自动重试：第 {next_attempt}/{max_attempts} 次尝试，"
            f"策略={strategy}，backoff={backoff_sec}s"
        ),
    )

    def _spawn_retry() -> None:
        if strategy == "fixed_backoff" and backoff_sec > 0:
            time.sleep(backoff_sec)
        start_run(
            workflow_id,
            owner_id=owner_id,
            retried_from_run_id=run_id,
            retry_origin_run_id=retry_origin,
            retry_attempt=next_attempt,
            retry_max_attempts=max_attempts,
            retry_strategy=strategy,
            retry_backoff_sec=backoff_sec,
        )

    executor.submit(_spawn_retry)
    return True


def _build_alerts(summary: dict, thresholds: dict | None = None) -> list[dict]:
    t = {**DEFAULT_ALERT_THRESHOLDS, **(thresholds or {})}
    alerts: list[dict] = []
    if int(summary.get("p95_node_duration_ms", 0)) >= int(t["p95_node_duration_ms"]):
        alerts.append(
            {
                "code": "A_RUN_P95_SLOW",
                "level": "warn",
                "message": f"P95 节点耗时过高: {summary.get('p95_node_duration_ms')}ms",
            }
        )
    if int(summary.get("failed_nodes", 0)) >= int(t["failed_nodes"]):
        alerts.append(
            {
                "code": "A_RUN_NODE_FAILED",
                "level": "error",
                "message": f"失败节点数告警: {summary.get('failed_nodes')}",
            }
        )
    if int(summary.get("warn_logs", 0)) >= int(t["warn_logs"]):
        alerts.append(
            {
                "code": "A_RUN_WARN_LOGS",
                "level": "warn",
                "message": f"告警日志数偏高: {summary.get('warn_logs')}",
            }
        )
    if int(summary.get("error_logs", 0)) >= int(t["error_logs"]):
        alerts.append(
            {
                "code": "A_RUN_ERROR_LOGS",
                "level": "error",
                "message": f"错误日志数告警: {summary.get('error_logs')}",
            }
        )
    return alerts


def _refresh_run_observability(run_id: str, workflow_id: str) -> dict:
    with Session(engine) as session:
        node_states = list(
            session.exec(select(WorkflowNodeState).where(WorkflowNodeState.run_id == run_id))
        )
        run_logs = list(session.exec(select(RunLog).where(RunLog.run_id == run_id)))
        durations = [int(item.duration_ms) for item in node_states if int(item.duration_ms) > 0]
        failure_states = [item for item in node_states if item.status == "failed"]
        warn_logs = [item for item in run_logs if item.level.upper() == "WARN"]
        error_logs = [item for item in run_logs if item.level.upper() == "ERROR"]

        slowest = max(node_states, key=lambda x: int(x.duration_ms or 0), default=None)
        failure_counter: dict[str, int] = {}
        for item in failure_states:
            key = f"{item.error_code or ERROR_NODE_EXECUTION}:{item.message}"
            failure_counter[key] = failure_counter.get(key, 0) + 1
        failure_reasons = [
            {"reason": key.split(":", 1)[1], "error_code": key.split(":", 1)[0], "count": count}
            for key, count in sorted(failure_counter.items(), key=lambda x: x[1], reverse=True)
        ][:5]

        summary = {
            "run_id": run_id,
            "workflow_id": workflow_id,
            "total_nodes": len(node_states),
            "success_nodes": len([item for item in node_states if item.status == "success"]),
            "failed_nodes": len(failure_states),
            "warn_logs": len(warn_logs),
            "error_logs": len(error_logs),
            "total_duration_ms": int(sum(durations)),
            "avg_node_duration_ms": int(np.mean(durations)) if durations else 0,
            "p95_node_duration_ms": int(np.percentile(durations, 95)) if durations else 0,
            "slowest_node": (
                {
                    "node_id": slowest.node_id,
                    "node_name": slowest.node_name,
                    "duration_ms": int(slowest.duration_ms or 0),
                }
                if slowest
                else None
            ),
            "failure_reasons": failure_reasons,
            "updated_at": datetime.utcnow().isoformat(),
        }
        summary["alerts"] = _build_alerts(summary)
        run = session.get(Run, run_id)
        if run:
            run.observability = summary
            run.updated_at = datetime.utcnow()
            session.add(run)
            session.commit()
        return summary


def _update_workflow_status(workflow_id: str, status: str) -> None:
    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        if not workflow:
            return
        workflow.status = status
        workflow.updated_at = datetime.utcnow()
        if status in {"running", "published"}:
            workflow.last_run = datetime.utcnow()
        session.add(workflow)
        session.commit()


def _save_report(workflow_id: str, workflow_name: str, payload: dict) -> None:
    with Session(engine) as session:
        report = session.get(Report, workflow_id)
        if report is None:
            report = Report(
                workflow_id=workflow_id,
                workflow_name=workflow_name,
                metrics=payload.get("metrics", []),
                equity_series=payload.get("equity_series", []),
                layer_return=payload.get("layer_return", []),
                updated_at=datetime.utcnow(),
            )
        else:
            report.workflow_name = workflow_name
            report.metrics = payload.get("metrics", [])
            report.equity_series = payload.get("equity_series", [])
            report.layer_return = payload.get("layer_return", [])
            report.updated_at = datetime.utcnow()
        session.add(report)
        session.commit()


def _upsert_node_state(
    run_id: str,
    workflow_id: str,
    node_id: str,
    node_name: str,
    *,
    status: str,
    message: str,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    duration_ms: int = 0,
    error_code: str | None = None,
) -> None:
    with Session(engine) as session:
        state = session.exec(
            select(WorkflowNodeState).where(
                WorkflowNodeState.run_id == run_id,
                WorkflowNodeState.node_id == node_id,
            )
        ).first()
        if state is None:
            state = WorkflowNodeState(
                id=f"ns-{uuid.uuid4().hex[:10]}",
                run_id=run_id,
                workflow_id=workflow_id,
                node_id=node_id,
                node_name=node_name,
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                error_code=error_code,
                message=message,
            )
        else:
            state.status = status
            state.message = message
            state.error_code = error_code
            if started_at is not None:
                state.started_at = started_at
            if finished_at is not None:
                state.finished_at = finished_at
            if duration_ms:
                state.duration_ms = duration_ms
        session.add(state)
        session.commit()


def _build_order(workflow: Workflow) -> list[str]:
    graph = workflow.graph or {}
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    dag = nx.DiGraph()
    for node in nodes:
        dag.add_node(node["id"], label=node.get("label", node["id"]))
    for edge in edges:
        dag.add_edge(edge["source"], edge["target"])
    if len(nodes) == 0:
        return []
    if not nx.is_directed_acyclic_graph(dag):
        raise ValueError(f"{ERROR_GRAPH_CYCLE}: 工作流图中存在环，无法执行")
    return list(nx.topological_sort(dag))


def _node_label_map(workflow: Workflow) -> dict[str, str]:
    return {n["id"]: n.get("label", n["id"]) for n in (workflow.graph or {}).get("nodes", [])}


def _node_payload_map(workflow: Workflow) -> dict[str, dict]:
    return {n["id"]: n for n in (workflow.graph or {}).get("nodes", [])}


def _nodespec_map(session: Session) -> dict[str, dict]:
    rows = list(session.exec(select(NodeSpec)))
    return {
        row.id: {
            "id": row.id,
            "name": row.name,
            "category": row.category,
            "inputs": row.inputs,
            "outputs": row.outputs,
            "params": row.params,
        }
        for row in rows
    }


def _resolve_artifact_params(session: Session, workflow_id: str, node_payload: dict) -> tuple[dict, list[dict]]:
    params = dict(node_payload.get("params") or {})
    warnings: list[dict] = []
    artifact_id = params.get("artifactId") or params.get("artifact_id")
    logical_key = params.get("artifactKey") or params.get("logical_key")
    artifact_version = params.get("artifactVersion")

    artifact: UploadedArtifact | None = None
    if artifact_id:
        artifact = session.get(UploadedArtifact, str(artifact_id))
        if artifact is None:
            warnings.append(
                {
                    "code": WARN_ARTIFACT_RESOLVE,
                    "message": f"节点 {node_payload.get('label', node_payload.get('id'))} 绑定制品不存在: {artifact_id}",
                }
            )
            return params, warnings
    elif logical_key:
        query = select(UploadedArtifact).where(
            UploadedArtifact.workflow_id == workflow_id,
            UploadedArtifact.logical_key == str(logical_key),
        )
        kind = params.get("artifactKind")
        if kind:
            query = query.where(UploadedArtifact.kind == str(kind))
        rows = list(session.exec(query.order_by(UploadedArtifact.version.desc(), UploadedArtifact.created_at.desc())))
        if artifact_version is not None:
            rows = [row for row in rows if int(row.version) == int(artifact_version)]
        if rows:
            artifact = next((row for row in rows if row.is_active), rows[0])
        else:
            warnings.append(
                {
                    "code": WARN_ARTIFACT_RESOLVE,
                    "message": f"节点 {node_payload.get('label', node_payload.get('id'))} 未找到逻辑制品: {logical_key}",
                }
            )
            return params, warnings
    else:
        return params, warnings

    if artifact.workflow_id and artifact.workflow_id != workflow_id:
        warnings.append(
            {
                "code": WARN_ARTIFACT_RESOLVE,
                "message": f"节点 {node_payload.get('label', node_payload.get('id'))} 绑定了其他工作流制品，已忽略",
            }
        )
        return params, warnings

    params["artifactId"] = artifact.id
    params["artifactKey"] = artifact.logical_key
    params["artifactVersion"] = artifact.version
    params["artifactName"] = artifact.file_name
    params["artifactPath"] = artifact.file_path
    params["path"] = artifact.file_path if "path" in params or "model_upload" in str(node_payload.get("nodeSpecId", "")) else params.get("path")
    if "artifact_path" in params:
        params["artifact_path"] = artifact.file_path
    return params, warnings


def execute_run(run_id: str, workflow_id: str) -> None:
    started = time.time()
    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        if not workflow:
            _update_run(run_id, status="failed", message="工作流不存在")
            _append_run_log(
                run_id,
                workflow_id,
                level="ERROR",
                message="工作流不存在",
                error_code=ERROR_RUN_NOT_FOUND,
            )
            return
        run = session.get(Run, run_id)
        if not run:
            return
        if run.status == "cancelled" or run.cancel_requested:
            run.status = "cancelled"
            run.message = "任务已取消（执行前）"
            run.updated_at = datetime.utcnow()
            session.add(run)
            session.commit()
            _append_run_log(
                run_id,
                workflow_id,
                level="WARN",
                message="任务在执行前被取消",
                error_code=ERROR_RUN_CANCELLED,
            )
            _update_workflow_status(workflow_id, "draft")
            return

    _update_workflow_status(workflow_id, "running")
    _update_run(run_id, status="running", message="开始执行工作流")
    _append_run_log(run_id, workflow_id, level="INFO", message="调度成功，准备执行 DAG")

    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        assert workflow is not None
        try:
            order = _build_order(workflow)
            labels = _node_label_map(workflow)
            nodes_payload = _node_payload_map(workflow)
            nodespec_map = _nodespec_map(session)
            contract_result = compile_workflow_contract(workflow.graph or {}, nodespec_map, strict=False)
            ctx = RunContext()
            _append_run_log(run_id, workflow_id, level="INFO", message=f"执行顺序: {order}")
            for item in contract_result.get("warnings", []):
                _append_run_log(
                    run_id,
                    workflow_id,
                    level="WARN",
                    message=item["message"],
                    error_code=item.get("code"),
                    detail=item.get("detail"),
                )
            for item in contract_result.get("errors", []):
                _append_run_log(
                    run_id,
                    workflow_id,
                    level="ERROR",
                    message=item["message"],
                    error_code=item.get("code"),
                    detail=item.get("detail"),
                )
            if any(item.get("code") == ERROR_COMPILE_CYCLE for item in contract_result.get("errors", [])):
                raise ValueError(f"{ERROR_GRAPH_CYCLE}: 工作流图中存在环，无法执行")

            for node_id in order:
                if _is_cancel_requested(run_id):
                    raise ValueError(f"{ERROR_RUN_CANCELLED}: 收到取消请求，运行已停止")
                node_payload = nodes_payload.get(node_id, {"id": node_id, "label": labels.get(node_id, node_id), "params": {}})
                node_name = node_payload.get("label", labels.get(node_id, node_id))
                node_spec = nodespec_map.get(node_payload.get("nodeSpecId", ""))
                resolved_params, resolve_warnings = _resolve_artifact_params(session, workflow_id, node_payload)
                node_payload = {**node_payload, "params": resolved_params}
                node_started = datetime.utcnow()
                _upsert_node_state(
                    run_id,
                    workflow_id,
                    node_id,
                    node_name,
                    status="running",
                    message="节点执行中",
                    started_at=node_started,
                )
                _update_run(run_id, status="running", message=f"执行中: {node_name}")
                _append_run_log(run_id, workflow_id, level="INFO", message=f"开始执行节点 {node_name}", node_id=node_id, node_name=node_name)
                for item in resolve_warnings:
                    _append_run_log(
                        run_id,
                        workflow_id,
                        level="WARN",
                        message=item["message"],
                        node_id=node_id,
                        node_name=node_name,
                        error_code=item.get("code"),
                        detail=item.get("detail"),
                    )

                start_node_ts = time.time()
                try:
                    node_warnings = execute_node(node_payload, node_spec, ctx)
                except Exception as exc:
                    node_cost_ms = int((time.time() - start_node_ts) * 1000)
                    error_code, error_msg = _parse_error(exc, default_code=ERROR_NODE_EXECUTION)
                    _record_metric_point(
                        run_id,
                        workflow_id,
                        "node_duration_ms",
                        node_cost_ms,
                        {"node_id": node_id, "node_name": node_name, "status": "failed", "error_code": error_code},
                    )
                    _record_metric_point(
                        run_id,
                        workflow_id,
                        "node_failure",
                        1.0,
                        {"node_id": node_id, "node_name": node_name, "error_code": error_code},
                    )
                    _upsert_node_state(
                        run_id,
                        workflow_id,
                        node_id,
                        node_name,
                        status="failed",
                        message=error_msg,
                        finished_at=datetime.utcnow(),
                        duration_ms=node_cost_ms,
                        error_code=error_code,
                    )
                    _append_run_log(
                        run_id,
                        workflow_id,
                        level="ERROR",
                        message=f"节点失败 {node_name}: {error_msg}",
                        node_id=node_id,
                        node_name=node_name,
                        error_code=error_code,
                    )
                    raise

                node_cost_ms = int((time.time() - start_node_ts) * 1000)
                _record_metric_point(
                    run_id,
                    workflow_id,
                    "node_duration_ms",
                    node_cost_ms,
                    {"node_id": node_id, "node_name": node_name, "status": "success"},
                )
                _record_metric_point(
                    run_id,
                    workflow_id,
                    "node_success",
                    1.0,
                    {"node_id": node_id, "node_name": node_name},
                )
                for item in node_warnings:
                    _append_run_log(
                        run_id,
                        workflow_id,
                        level="WARN",
                        message=item.get("message", ""),
                        node_id=node_id,
                        node_name=node_name,
                        error_code=item.get("code"),
                        detail=item.get("detail"),
                    )

                _upsert_node_state(
                    run_id,
                    workflow_id,
                    node_id,
                    node_name,
                    status="success",
                    message="节点执行成功",
                    finished_at=datetime.utcnow(),
                    duration_ms=node_cost_ms,
                )
                _append_run_log(
                    run_id,
                    workflow_id,
                    level="INFO",
                    message=f"节点完成 {node_name}，耗时 {node_cost_ms}ms",
                    node_id=node_id,
                    node_name=node_name,
                )

            if ctx.report is None:
                handle_backtest(ctx)
                _append_run_log(run_id, workflow_id, level="INFO", message="执行后置回测并生成报告")

            _save_report(workflow_id, workflow.name, ctx.report or {})
            duration = _fmt_duration(started, time.time())
            summary = _refresh_run_observability(run_id, workflow_id)
            _record_metric_point(run_id, workflow_id, "run_total_duration_ms", float(summary.get("total_duration_ms", 0)))
            _record_metric_point(run_id, workflow_id, "run_p95_node_ms", float(summary.get("p95_node_duration_ms", 0)))
            _record_metric_point(run_id, workflow_id, "run_failed_nodes", float(summary.get("failed_nodes", 0)))
            _record_metric_point(run_id, workflow_id, "run_warn_logs", float(summary.get("warn_logs", 0)))
            _record_metric_point(run_id, workflow_id, "run_error_logs", float(summary.get("error_logs", 0)))
            for alert in summary.get("alerts", []):
                _record_metric_point(
                    run_id,
                    workflow_id,
                    "run_alert",
                    1.0,
                    {"code": alert.get("code"), "level": alert.get("level"), "message": alert.get("message")},
                )
            _update_run(run_id, status="success", message="执行完成，报告已生成", duration=duration, observability=summary)
            _append_run_log(run_id, workflow_id, level="INFO", message="运行成功结束")
            _update_workflow_status(workflow_id, "published")
        except Exception as exc:
            duration = _fmt_duration(started, time.time())
            error_code, error_msg = _parse_error(exc, default_code=ERROR_RUN_INTERNAL)
            summary = _refresh_run_observability(run_id, workflow_id)
            if error_code == ERROR_RUN_CANCELLED:
                _update_run(
                    run_id,
                    status="cancelled",
                    message="任务已取消",
                    duration=duration,
                    observability=summary,
                )
                _append_run_log(
                    run_id,
                    workflow_id,
                    level="WARN",
                    message=f"运行取消: {error_msg}",
                    error_code=error_code,
                )
            else:
                _record_metric_point(run_id, workflow_id, "run_failure", 1.0, {"error_code": error_code})
                _update_run(
                    run_id,
                    status="failed",
                    message=f"执行失败[{error_code}]: {error_msg}",
                    duration=duration,
                    observability=summary,
                )
                _append_run_log(
                    run_id,
                    workflow_id,
                    level="ERROR",
                    message=f"运行失败: {error_msg}",
                    error_code=error_code,
                )
                _schedule_retry_after_failure(run_id, workflow_id, error_code=error_code)
            _update_workflow_status(workflow_id, "draft")


def start_run(
    workflow_id: str,
    *,
    owner_id: str | None = None,
    retried_from_run_id: str | None = None,
    retry_origin_run_id: str | None = None,
    retry_attempt: int = 1,
    retry_max_attempts: int = 1,
    retry_strategy: str = "immediate",
    retry_backoff_sec: int = 0,
) -> Run:
    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        if not workflow:
            raise ValueError("工作流不存在")
        strategy = retry_strategy if retry_strategy in {"immediate", "fixed_backoff"} else "immediate"
        run = Run(
            id=f"run-{uuid.uuid4().hex[:8]}",
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            status="queued",
            duration="00m 00s",
            created_at=datetime.utcnow(),
            owner_id=owner_id or workflow.owner_id,
            updated_at=datetime.utcnow(),
            message="任务已进入队列，等待调度",
            logs=["[INFO] run 已创建"],
            observability={},
            cancel_requested=False,
            retried_from_run_id=retried_from_run_id,
            retry_origin_run_id=retry_origin_run_id,
            retry_attempt=max(1, int(retry_attempt)),
            retry_max_attempts=max(1, min(5, int(retry_max_attempts))),
            retry_strategy=strategy,
            retry_backoff_sec=max(0, min(300, int(retry_backoff_sec))),
        )
        session.add(run)
        session.commit()
        session.refresh(run)

    _append_run_log(run.id, workflow_id, level="INFO", message="run 记录已创建")
    future = executor.submit(execute_run, run.id, workflow_id)
    _track_future(run.id, future)
    return run


def cancel_run(run_id: str) -> Run | None:
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if not run:
            return None
        if run.status in {"success", "failed", "cancelled"}:
            return run
        run.cancel_requested = True
        run.updated_at = datetime.utcnow()
        cancelled_in_queue = False
        if run.status == "queued":
            cancelled_in_queue = _try_cancel_future(run_id)
            run.status = "cancelled"
            run.message = "任务已取消（队列中）"
            run.duration = run.duration or "00m 00s"
        session.add(run)
        session.commit()
        session.refresh(run)

    _append_run_log(
        run.id,
        run.workflow_id,
        level="WARN",
        message="收到取消请求" + ("（已从队列移除）" if cancelled_in_queue else "（等待当前节点结束）"),
        error_code=ERROR_RUN_CANCELLED,
    )
    if run.status == "cancelled":
        _update_workflow_status(run.workflow_id, "draft")
    return run


def retry_run(
    run_id: str,
    *,
    owner_id: str | None = None,
    strategy: str = "immediate",
    max_attempts: int = 1,
    backoff_sec: int = 0,
) -> Run:
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if not run:
            raise ValueError("run not found")
        if run.status not in {"failed", "cancelled"}:
            raise ValueError("only failed/cancelled run can retry")
        workflow_id = run.workflow_id
        origin = run.retry_origin_run_id or run.id
    return start_run(
        workflow_id,
        owner_id=owner_id or run.owner_id,
        retried_from_run_id=run_id,
        retry_origin_run_id=origin,
        retry_attempt=1,
        retry_max_attempts=max(1, min(5, int(max_attempts))),
        retry_strategy=strategy,
        retry_backoff_sec=max(0, min(300, int(backoff_sec))),
    )


def list_runs(session: Session) -> list[Run]:
    return list(session.exec(select(Run).order_by(Run.created_at.desc())))


def list_run_logs(session: Session, run_id: str) -> list[RunLog]:
    return list(session.exec(select(RunLog).where(RunLog.run_id == run_id).order_by(RunLog.created_at.asc())))


def list_node_states(session: Session, run_id: str) -> list[WorkflowNodeState]:
    return list(
        session.exec(
            select(WorkflowNodeState)
            .where(WorkflowNodeState.run_id == run_id)
            .order_by(WorkflowNodeState.started_at.asc())
        )
    )


def get_run_observability(session: Session, run_id: str) -> dict:
    run = session.get(Run, run_id)
    if not run:
        return {}
    return run.observability or {}


def get_run_alerts(session: Session, run_id: str, thresholds: dict | None = None) -> list[dict]:
    summary = get_run_observability(session, run_id)
    if not summary:
        return []
    return _build_alerts(summary, thresholds=thresholds)


def list_run_metric_points(
    session: Session,
    run_id: str,
    *,
    metric_name: str | None = None,
    limit: int = 500,
) -> list[RunMetricPoint]:
    query = select(RunMetricPoint).where(RunMetricPoint.run_id == run_id).order_by(RunMetricPoint.created_at.asc())
    if metric_name:
        query = query.where(RunMetricPoint.metric_name == metric_name)
    rows = list(session.exec(query))
    return rows[-max(1, min(5000, limit)) :]


def list_workflow_metric_points(
    session: Session,
    workflow_id: str,
    *,
    metric_name: str | None = None,
    limit: int = 500,
) -> list[RunMetricPoint]:
    query = select(RunMetricPoint).where(RunMetricPoint.workflow_id == workflow_id).order_by(RunMetricPoint.created_at.asc())
    if metric_name:
        query = query.where(RunMetricPoint.metric_name == metric_name)
    rows = list(session.exec(query))
    return rows[-max(1, min(5000, limit)) :]
