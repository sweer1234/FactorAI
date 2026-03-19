from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import re
import time
import uuid

import networkx as nx
import numpy as np
from sqlmodel import Session, select

from ..db import engine
from ..models import NodeSpec, Report, Run, RunLog, UploadedArtifact, Workflow, WorkflowNodeState
from .node_handlers import RunContext, execute_node, handle_backtest


executor = ThreadPoolExecutor(max_workers=4)

ERROR_GRAPH_CYCLE = "E_GRAPH_CYCLE"
ERROR_CONTRACT_PORT = "E_CONTRACT_PORT"
ERROR_CONTRACT_TYPE = "E_CONTRACT_TYPE"
ERROR_ARTIFACT_NOT_FOUND = "E_ARTIFACT_NOT_FOUND"
ERROR_ARTIFACT_SCOPE = "E_ARTIFACT_SCOPE"
ERROR_NODE_EXECUTION = "E_NODE_EXECUTION"
ERROR_RUN_INTERNAL = "E_RUN_INTERNAL"
ERROR_RUN_NOT_FOUND = "E_RUN_NOT_FOUND"

WARN_CONTRACT_PORT = "W_CONTRACT_PORT"
WARN_CONTRACT_TYPE = "W_CONTRACT_TYPE"
WARN_ARTIFACT_RESOLVE = "W_ARTIFACT_RESOLVE"

PORT_FAMILY_MAP = {
    "dataset": "table",
    "market_df": "table",
    "feature_df": "table",
    "label_df": "table",
    "formula_df": "table",
    "pred_df": "table",
    "pred_a": "table",
    "pred_b": "table",
    "df_factor": "table",
    "factor_pool": "table",
    "weighted_factor": "table",
    "factor_a": "table",
    "factor_b": "table",
    "split_formula_df": "table",
    "converted_formula": "table",
    "industry_feature_df": "table",
    "industry_factor": "table",
    "graph_feature_df": "table",
    "model_obj": "model",
    "alphagen_obj": "model",
    "best_params": "model",
    "backtest_report": "report",
    "analysis_report": "report",
    "result_json": "report",
    "report_json": "report",
    "corr_matrix": "report",
    "ic_report": "report",
    "artifact_url": "artifact",
    "contest_artifact": "artifact",
}

PORT_DATA_TYPE_MAP = {
    "market_df": "market_table",
    "feature_df": "feature_table",
    "label_df": "label_table",
    "formula_df": "formula_table",
    "pred_df": "prediction_table",
    "pred_a": "prediction_table",
    "pred_b": "prediction_table",
    "df_factor": "factor_table",
    "factor_a": "factor_table",
    "factor_b": "factor_table",
    "factor_pool": "factor_pool_table",
    "weighted_factor": "factor_table",
    "model_obj": "model_binary",
    "alphagen_obj": "model_binary",
    "best_params": "model_param",
    "backtest_report": "report_table",
    "analysis_report": "report_table",
    "result_json": "json_report",
    "report_json": "json_report",
    "corr_matrix": "corr_report",
    "artifact_url": "artifact_url",
    "contest_artifact": "artifact_package",
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


def _port_family(port: str) -> str:
    return PORT_FAMILY_MAP.get(port, port)


def _port_dtype(port: str) -> str:
    return PORT_DATA_TYPE_MAP.get(port, port)


def _validate_graph_connections(workflow: Workflow, nodespec_map: dict[str, dict]) -> list[dict]:
    graph = workflow.graph or {}
    node_map = _node_payload_map(workflow)
    warnings: list[dict] = []
    for edge in graph.get("edges", []):
        source = node_map.get(edge.get("source"))
        target = node_map.get(edge.get("target"))
        if not source or not target:
            continue
        source_spec = nodespec_map.get(source.get("nodeSpecId", ""))
        target_spec = nodespec_map.get(target.get("nodeSpecId", ""))
        if not source_spec or not target_spec:
            continue
        outputs = list(source_spec.get("outputs", []))
        inputs = list(target_spec.get("inputs", []))
        if not outputs or not inputs:
            continue

        family_pairs = [(out, inp) for out in outputs for inp in inputs if _port_family(out) == _port_family(inp)]
        if not family_pairs:
            warnings.append(
                {
                    "code": WARN_CONTRACT_PORT,
                    "message": (
                        f"连线契约告警: {source.get('label')}({edge.get('source')}) 输出 {outputs} 与 "
                        f"{target.get('label')}({edge.get('target')}) 输入 {inputs} 家族不匹配"
                    ),
                    "detail": {"edge_id": edge.get("id"), "outputs": outputs, "inputs": inputs},
                }
            )
            continue

        type_pairs = [(out, inp) for out, inp in family_pairs if _port_dtype(out) == _port_dtype(inp)]
        if not type_pairs:
            warnings.append(
                {
                    "code": WARN_CONTRACT_TYPE,
                    "message": (
                        f"连线类型告警: {source.get('label')} -> {target.get('label')} "
                        f"家族可兼容但具体类型不一致，按兼容模式继续"
                    ),
                    "detail": {"edge_id": edge.get("id"), "outputs": outputs, "inputs": inputs},
                }
            )
    return warnings


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
            contract_warnings = _validate_graph_connections(workflow, nodespec_map)
            ctx = RunContext()
            _append_run_log(run_id, workflow_id, level="INFO", message=f"执行顺序: {order}")
            for item in contract_warnings:
                _append_run_log(
                    run_id,
                    workflow_id,
                    level="WARN",
                    message=item["message"],
                    error_code=item.get("code"),
                    detail=item.get("detail"),
                )

            for node_id in order:
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
            _update_run(run_id, status="success", message="执行完成，报告已生成", duration=duration, observability=summary)
            _append_run_log(run_id, workflow_id, level="INFO", message="运行成功结束")
            _update_workflow_status(workflow_id, "published")
        except Exception as exc:
            duration = _fmt_duration(started, time.time())
            error_code, error_msg = _parse_error(exc, default_code=ERROR_RUN_INTERNAL)
            summary = _refresh_run_observability(run_id, workflow_id)
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
            _update_workflow_status(workflow_id, "draft")


def start_run(workflow_id: str) -> Run:
    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        if not workflow:
            raise ValueError("工作流不存在")
        run = Run(
            id=f"run-{uuid.uuid4().hex[:8]}",
            workflow_id=workflow.id,
            workflow_name=workflow.name,
            status="queued",
            duration="00m 00s",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            message="任务已进入队列，等待调度",
            logs=["[INFO] run 已创建"],
            observability={},
        )
        session.add(run)
        session.commit()
        session.refresh(run)

    _append_run_log(run.id, workflow_id, level="INFO", message="run 记录已创建")
    executor.submit(execute_run, run.id, workflow_id)
    return run


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
