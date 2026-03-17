from __future__ import annotations

from datetime import datetime
import uuid

from sqlmodel import Session, select

from .models import NodeSpec, Report, Run, RunLog, Template, TemplateVersion, Workflow
from .services.catalog import NODE_LIBRARY_CATALOG, REPORT_SEED_PAYLOAD, TEMPLATE_CATALOG, WORKFLOW_SEED_CATALOG


def _dt(text: str | None) -> datetime | None:
    if not text:
        return None
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")


def _seed_node_specs(session: Session) -> None:
    existing_ids = set(session.exec(select(NodeSpec.id)).all())
    for row in NODE_LIBRARY_CATALOG:
        if row["id"] in existing_ids:
            continue
        session.add(
            NodeSpec(
                id=row["id"],
                name=row["name"],
                category=row["category"],
                description=row["description"],
                inputs=row["inputs"],
                outputs=row["outputs"],
                params=row["params"],
                doc=row.get("doc", {}),
                runtime=row.get("runtime", {}),
                updated_at=datetime.utcnow(),
            )
        )
    session.commit()


def _seed_templates(session: Session) -> None:
    existing_ids = set(session.exec(select(Template.id)).all())
    existing_version_pairs = {
        (row[0], row[1])
        for row in session.exec(select(TemplateVersion.template_id, TemplateVersion.version)).all()
    }

    for row in TEMPLATE_CATALOG:
        if row["id"] in existing_ids:
            continue
        updated_at = _dt(row["updated_at"]) or datetime.utcnow()
        template = Template(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            tags=row["tags"],
            updated_at=updated_at,
            category=row["category"],
            official=row.get("official", True),
            template_group=row.get("template_group", "官方模板"),
            graph=row["graph"],
        )
        session.add(template)
        if (template.id, "1.0.0") not in existing_version_pairs:
            session.add(
                TemplateVersion(
                    id=f"tv-{uuid.uuid4().hex[:10]}",
                    template_id=template.id,
                    version="1.0.0",
                    changelog="初始化模板版本",
                    graph=template.graph,
                    created_at=updated_at,
                )
            )
    session.commit()


def _seed_workflows(session: Session) -> None:
    existing_ids = set(session.exec(select(Workflow.id)).all())

    for row in WORKFLOW_SEED_CATALOG:
        if row["id"] in existing_ids:
            continue
        session.add(
            Workflow(
                id=row["id"],
                name=row["name"],
                category=row["category"],
                tags=row["tags"],
                status=row["status"],
                updated_at=_dt(row["updated_at"]) or datetime.utcnow(),
                last_run=_dt(row.get("last_run")),
                description=row.get("description"),
                graph=row["graph"],
            )
        )
    session.commit()


def _seed_runs(session: Session) -> None:
    existing = session.exec(select(Run.id)).first()
    if existing:
        return
    now = datetime.utcnow()
    run = Run(
        id="run-901",
        workflow_id="wf-001",
        workflow_name="官方案例-6-超参搜索（运行中）",
        status="success",
        duration="01m 43s",
        created_at=now,
        updated_at=now,
        message="完成 9 个节点，生成回测报告。",
        logs=["[INFO] DAG 编排完成", "[INFO] 因子分析输出完成"],
    )
    session.add(run)
    session.add(
        RunLog(
            id=f"log-{uuid.uuid4().hex[:10]}",
            run_id=run.id,
            workflow_id=run.workflow_id,
            level="INFO",
            message="初始化运行记录",
            created_at=now,
        )
    )
    session.commit()


def _seed_reports(session: Session) -> None:
    existing = session.exec(select(Report.workflow_id)).first()
    if existing:
        return
    payload = REPORT_SEED_PAYLOAD
    session.add(
        Report(
            workflow_id="wf-001",
            workflow_name="官方案例-6-超参搜索（运行中）",
            metrics=payload["metrics"],
            equity_series=payload["equity_series"],
            layer_return=payload["layer_return"],
            updated_at=_dt(payload["updated_at"]) or datetime.utcnow(),
        )
    )
    session.commit()


def seed_if_empty(session: Session) -> None:
    _seed_node_specs(session)
    _seed_templates(session)
    _seed_workflows(session)
    _seed_runs(session)
    _seed_reports(session)
