from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from .config import settings
from .db import get_session
from .models import NodeSpec, Report, Run, RunLog, Template, UploadedArtifact, Workflow
from .schemas import (
    ArtifactRead,
    ArtifactRollbackRequest,
    ContractCompileRead,
    GraphUpdate,
    ContractIssueRead,
    NodeDefinitionRead,
    NodeStateRead,
    ReportRead,
    RunAlertsRead,
    RunMetricPointRead,
    RunLogRead,
    RunObservabilityRead,
    RunRead,
    TemplateRead,
    WorkflowCreate,
    WorkflowRead,
)
from .services.contract import compile_workflow_contract
from .services.execution import (
    get_run_alerts,
    get_run_observability,
    list_node_states,
    list_run_logs,
    list_run_metric_points,
    list_runs,
    list_workflow_metric_points,
    start_run,
)
from .services.node_library import NODE_LIBRARY


router = APIRouter()


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
        source_template_id=row.source_template_id,
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


@router.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


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
def get_workflows(session: Session = Depends(get_session)):
    rows = list(session.exec(select(Workflow).order_by(Workflow.updated_at.desc())))
    return [_workflow_to_read(row) for row in rows]


@router.get("/workflows/{workflow_id}", response_model=WorkflowRead)
def get_workflow(workflow_id: str, session: Session = Depends(get_session)):
    row = session.get(Workflow, workflow_id)
    if not row:
        raise HTTPException(status_code=404, detail="workflow not found")
    return _workflow_to_read(row)


@router.post("/workflows", response_model=WorkflowRead)
def create_workflow(payload: WorkflowCreate, session: Session = Depends(get_session)):
    workflow = Workflow(
        id=f"wf-{uuid.uuid4().hex[:8]}",
        name=payload.name.strip(),
        category=payload.category.strip() or "未分类",
        tags=payload.tags,
        status="draft",
        updated_at=datetime.utcnow(),
        description=payload.description,
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
):
    row = session.get(Workflow, workflow_id)
    if not row:
        raise HTTPException(status_code=404, detail="workflow not found")
    node_specs = list(session.exec(select(NodeSpec)))
    nodespec_map = {
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
    compile_result = compile_workflow_contract(payload.graph.model_dump(), nodespec_map, strict=strict_contract)
    if strict_contract and compile_result.get("errors"):
        raise HTTPException(
            status_code=400,
            detail={
                "message": "contract compile failed",
                "errors": compile_result["errors"],
            },
        )
    row.graph = payload.graph.model_dump()
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _workflow_to_read(row)


@router.get("/workflows/{workflow_id}/contract-compile", response_model=ContractCompileRead)
def compile_workflow_contract_check(
    workflow_id: str,
    strict: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    row = session.get(Workflow, workflow_id)
    if not row:
        raise HTTPException(status_code=404, detail="workflow not found")
    node_specs = list(session.exec(select(NodeSpec)))
    nodespec_map = {
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
    result = compile_workflow_contract(row.graph or {"nodes": [], "edges": []}, nodespec_map, strict=strict)
    return ContractCompileRead(
        valid=result.get("valid", False),
        strict=result.get("strict", strict),
        errors=[ContractIssueRead(**item) for item in result.get("errors", [])],
        warnings=[ContractIssueRead(**item) for item in result.get("warnings", [])],
        node_input_schemas=result.get("node_input_schemas", {}),
        node_output_schemas=result.get("node_output_schemas", {}),
        compiled_at=datetime.utcnow(),
    )


@router.post("/workflows/{workflow_id}/draft", response_model=WorkflowRead)
def save_draft(workflow_id: str, session: Session = Depends(get_session)):
    row = session.get(Workflow, workflow_id)
    if not row:
        raise HTTPException(status_code=404, detail="workflow not found")
    row.status = "draft"
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _workflow_to_read(row)


@router.post("/workflows/{workflow_id}/run", response_model=RunRead)
def run_workflow(workflow_id: str, session: Session = Depends(get_session)):
    row = session.get(Workflow, workflow_id)
    if not row:
        raise HTTPException(status_code=404, detail="workflow not found")
    run = start_run(workflow_id)
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


@router.post("/templates/{template_id}/clone", response_model=WorkflowRead)
def clone_template(template_id: str, session: Session = Depends(get_session)):
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
        description=template.description,
        source_template_id=template.id,
        graph=template.graph,
    )
    session.add(workflow)
    session.commit()
    session.refresh(workflow)
    return _workflow_to_read(workflow)


@router.get("/runs", response_model=list[RunRead])
def get_runs(session: Session = Depends(get_session)):
    rows = list_runs(session)
    return [_run_to_read(row) for row in rows]


@router.get("/runs/{run_id}", response_model=RunRead)
def get_run(run_id: str, session: Session = Depends(get_session)):
    row = session.get(Run, run_id)
    if not row:
        raise HTTPException(status_code=404, detail="run not found")
    return _run_to_read(row)


@router.get("/runs/{run_id}/logs", response_model=list[RunLogRead])
def get_run_logs(run_id: str, session: Session = Depends(get_session)):
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
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
def get_run_node_states(run_id: str, session: Session = Depends(get_session)):
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
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
def get_run_metrics(run_id: str, session: Session = Depends(get_session)):
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return RunObservabilityRead(
        run_id=run.id,
        workflow_id=run.workflow_id,
        summary=get_run_observability(session, run.id),
    )


@router.get("/runs/{run_id}/observability/alerts", response_model=RunAlertsRead)
def get_run_metric_alerts(
    run_id: str,
    p95_node_duration_ms: int | None = Query(default=None),
    failed_nodes: int | None = Query(default=None),
    warn_logs: int | None = Query(default=None),
    error_logs: int | None = Query(default=None),
    session: Session = Depends(get_session),
):
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    thresholds = {
        key: value
        for key, value in {
            "p95_node_duration_ms": p95_node_duration_ms,
            "failed_nodes": failed_nodes,
            "warn_logs": warn_logs,
            "error_logs": error_logs,
        }.items()
        if value is not None
    }
    alerts = get_run_alerts(session, run.id, thresholds=thresholds or None)
    return RunAlertsRead(run_id=run.id, workflow_id=run.workflow_id, alerts=alerts, thresholds=thresholds)


@router.get("/runs/{run_id}/observability/series", response_model=list[RunMetricPointRead])
def get_run_metric_series(
    run_id: str,
    metric_name: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
    session: Session = Depends(get_session),
):
    run = session.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
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
):
    workflow = session.get(Workflow, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="workflow not found")
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


@router.get("/reports/{workflow_id}", response_model=ReportRead | None)
def get_report(workflow_id: str, session: Session = Depends(get_session)):
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
    return [_artifact_to_read(row) for row in rows]


@router.get("/artifacts/{artifact_id}", response_model=ArtifactRead)
def get_artifact(artifact_id: str, session: Session = Depends(get_session)):
    row = session.get(UploadedArtifact, artifact_id)
    if not row:
        raise HTTPException(status_code=404, detail="artifact not found")
    return _artifact_to_read(row)


@router.post("/artifacts/{artifact_id}/rollback", response_model=ArtifactRead)
def rollback_artifact(
    artifact_id: str,
    payload: ArtifactRollbackRequest,
    session: Session = Depends(get_session),
):
    target = session.get(UploadedArtifact, artifact_id)
    if not target:
        raise HTTPException(status_code=404, detail="artifact not found")

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
def download_artifact(artifact_id: str, session: Session = Depends(get_session)):
    row = session.get(UploadedArtifact, artifact_id)
    if not row:
        raise HTTPException(status_code=404, detail="artifact not found")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact file missing")
    return FileResponse(path, filename=row.file_name)
