from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import time
import uuid

import networkx as nx
from sqlmodel import Session, select

from ..db import engine
from ..models import NodeSpec, Report, Run, RunLog, UploadedArtifact, Workflow, WorkflowNodeState
from .node_handlers import RunContext, execute_node, handle_backtest


executor = ThreadPoolExecutor(max_workers=4)


def _fmt_duration(start: float, end: float) -> str:
    seconds = max(1, int(end - start))
    return f"{seconds // 60:02d}m {seconds % 60:02d}s"


def _append_run_log(
    run_id: str,
    workflow_id: str,
    *,
    level: str,
    message: str,
    node_id: str | None = None,
    node_name: str | None = None,
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
                message=message,
                created_at=datetime.utcnow(),
            )
        )
        run = session.get(Run, run_id)
        if run:
            lines = list(run.logs or [])
            lines.append(f"[{level}] {message}")
            run.logs = lines[-200:]
            run.updated_at = datetime.utcnow()
            session.add(run)
        session.commit()


def _update_run(
    run_id: str,
    *,
    status: str,
    message: str,
    duration: str | None = None,
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
        session.add(run)
        session.commit()


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
                message=message,
            )
        else:
            state.status = status
            state.message = message
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
        raise ValueError("工作流图中存在环，无法执行")
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


def _validate_graph_connections(workflow: Workflow, nodespec_map: dict[str, dict]) -> list[str]:
    def normalize_port(port: str) -> str:
        table_ports = {
            "dataset",
            "market_df",
            "feature_df",
            "label_df",
            "formula_df",
            "pred_df",
            "df_factor",
            "factor_pool",
            "weighted_factor",
            "factor_a",
            "factor_b",
            "split_formula_df",
            "converted_formula",
            "industry_feature_df",
            "industry_factor",
            "graph_feature_df",
        }
        model_ports = {"model_obj", "alphagen_obj", "best_params"}
        report_ports = {"backtest_report", "analysis_report", "result_json", "report_json", "corr_matrix", "ic_report"}
        artifact_ports = {"artifact_url", "contest_artifact"}
        if port in table_ports:
            return "table"
        if port in model_ports:
            return "model"
        if port in report_ports:
            return "report"
        if port in artifact_ports:
            return "artifact"
        return port

    graph = workflow.graph or {}
    node_map = _node_payload_map(workflow)
    warnings: list[str] = []
    for edge in graph.get("edges", []):
        source = node_map.get(edge.get("source"))
        target = node_map.get(edge.get("target"))
        if not source or not target:
            continue
        source_spec = nodespec_map.get(source.get("nodeSpecId", ""))
        target_spec = nodespec_map.get(target.get("nodeSpecId", ""))
        if not source_spec or not target_spec:
            continue
        outputs = {normalize_port(item) for item in source_spec.get("outputs", [])}
        inputs = {normalize_port(item) for item in target_spec.get("inputs", [])}
        if outputs and inputs and outputs.isdisjoint(inputs):
            warnings.append(
                f"连线契约告警: {source.get('label')}({edge.get('source')}) 输出 {sorted(outputs)} 与 "
                f"{target.get('label')}({edge.get('target')}) 输入 {sorted(inputs)} 不匹配，已按兼容模式继续"
            )
    return warnings


def _resolve_artifact_params(session: Session, workflow_id: str, node_payload: dict) -> tuple[dict, list[str]]:
    params = dict(node_payload.get("params") or {})
    warnings: list[str] = []
    artifact_id = params.get("artifactId") or params.get("artifact_id")
    if not artifact_id:
        return params, warnings

    artifact = session.get(UploadedArtifact, str(artifact_id))
    if artifact is None:
        warnings.append(f"节点 {node_payload.get('label', node_payload.get('id'))} 绑定的制品不存在: {artifact_id}")
        return params, warnings
    if artifact.workflow_id and artifact.workflow_id != workflow_id:
        warnings.append(
            f"节点 {node_payload.get('label', node_payload.get('id'))} 绑定了其他工作流制品 {artifact_id}，已忽略绑定"
        )
        return params, warnings

    params["artifactId"] = artifact.id
    params["artifactName"] = artifact.file_name
    params["artifactPath"] = artifact.file_path
    if "path" in params or "model_upload" in str(node_payload.get("nodeSpecId", "")):
        params["path"] = artifact.file_path
    if "artifact_path" in params:
        params["artifact_path"] = artifact.file_path
    return params, warnings


def execute_run(run_id: str, workflow_id: str) -> None:
    started = time.time()
    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        if not workflow:
            _update_run(run_id, status="failed", message="工作流不存在")
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
                _append_run_log(run_id, workflow_id, level="WARN", message=item)

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
                    _append_run_log(run_id, workflow_id, level="WARN", message=item, node_id=node_id, node_name=node_name)

                start_node_ts = time.time()
                node_warnings = execute_node(node_payload, node_spec, ctx)
                node_cost_ms = int((time.time() - start_node_ts) * 1000)
                for item in node_warnings:
                    _append_run_log(run_id, workflow_id, level="WARN", message=item, node_id=node_id, node_name=node_name)

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
            _update_run(run_id, status="success", message="执行完成，报告已生成", duration=duration)
            _append_run_log(run_id, workflow_id, level="INFO", message="运行成功结束")
            _update_workflow_status(workflow_id, "published")
        except Exception as exc:
            duration = _fmt_duration(started, time.time())
            _update_run(run_id, status="failed", message=f"执行失败: {exc}", duration=duration)
            _append_run_log(run_id, workflow_id, level="ERROR", message=f"运行失败: {exc}")
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
