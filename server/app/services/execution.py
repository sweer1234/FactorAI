from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import time
import uuid

import networkx as nx
from sqlmodel import Session, select

from ..db import engine
from ..models import Report, Run, Workflow
from .node_handlers import RunContext, execute_node_by_label


executor = ThreadPoolExecutor(max_workers=4)


def _fmt_duration(start: float, end: float) -> str:
    seconds = max(1, int(end - start))
    return f"{seconds // 60:02d}m {seconds % 60:02d}s"


def _update_run(run_id: str, *, status: str, message: str, logs: list[str] | None = None, duration: str | None = None):
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if not run:
            return
        run.status = status
        run.message = message
        if logs is not None:
            run.logs = logs
        if duration is not None:
            run.duration = duration
        session.add(run)
        session.commit()


def _update_workflow_status(workflow_id: str, status: str):
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


def _save_report(workflow_id: str, workflow_name: str, payload: dict):
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


def execute_run(run_id: str, workflow_id: str) -> None:
    started = time.time()
    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        if not workflow:
            _update_run(run_id, status="failed", message="工作流不存在")
            return

    _update_workflow_status(workflow_id, "running")
    _update_run(run_id, status="running", message="开始执行工作流", logs=["[INFO] 调度成功，开始执行"])

    with Session(engine) as session:
        workflow = session.get(Workflow, workflow_id)
        assert workflow is not None
        try:
            order = _build_order(workflow)
            labels = _node_label_map(workflow)
            ctx = RunContext()
            logs = [f"[INFO] 执行顺序: {order}"]

            for node_id in order:
                label = labels.get(node_id, node_id)
                logs.append(f"[INFO] 执行节点: {label}({node_id})")
                _update_run(run_id, status="running", message=f"执行中: {label}", logs=logs[-20:])
                execute_node_by_label(label, ctx)
                logs.extend(ctx.logs[-2:])

            if ctx.report is None:
                from .node_handlers import handle_backtest

                handle_backtest(ctx)
                logs.extend(ctx.logs[-2:])

            _save_report(workflow_id, workflow.name, ctx.report or {})
            duration = _fmt_duration(started, time.time())
            _update_run(run_id, status="success", message="执行完成，报告已生成", logs=logs[-50:], duration=duration)
            _update_workflow_status(workflow_id, "published")
        except Exception as exc:
            duration = _fmt_duration(started, time.time())
            _update_run(
                run_id,
                status="failed",
                message=f"执行失败: {exc}",
                logs=[f"[ERROR] {exc}"],
                duration=duration,
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
            message="任务已进入队列，等待调度",
            logs=["[INFO] run 已创建"],
        )
        session.add(run)
        session.commit()
        session.refresh(run)

    executor.submit(execute_run, run.id, workflow_id)
    return run


def list_runs(session: Session) -> list[Run]:
    return list(session.exec(select(Run).order_by(Run.created_at.desc())))
