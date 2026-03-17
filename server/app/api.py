from __future__ import annotations

from datetime import datetime
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
    GraphUpdate,
    NodeDefinitionRead,
    NodeStateRead,
    ReportRead,
    RunLogRead,
    RunRead,
    TemplateRead,
    WorkflowCreate,
    WorkflowRead,
)
from .services.execution import list_node_states, list_run_logs, list_runs, start_run
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
def update_workflow_graph(workflow_id: str, payload: GraphUpdate, session: Session = Depends(get_session)):
    row = session.get(Workflow, workflow_id)
    if not row:
        raise HTTPException(status_code=404, detail="workflow not found")
    row.graph = payload.graph.model_dump()
    row.updated_at = datetime.utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _workflow_to_read(row)


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
            message=row.message,
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

    row = UploadedArtifact(
        id=artifact_id,
        workflow_id=workflow_id,
        kind=kind,
        file_name=file.filename,
        file_size=len(content),
        file_path=str(save_path),
        created_at=datetime.utcnow(),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return ArtifactRead(
        id=row.id,
        workflow_id=row.workflow_id,
        kind=row.kind,
        file_name=row.file_name,
        file_size=row.file_size,
        created_at=row.created_at,
    )


@router.get("/artifacts", response_model=list[ArtifactRead])
def list_artifacts(
    session: Session = Depends(get_session),
    workflow_id: str | None = Query(default=None),
    kind: str | None = Query(default=None),
):
    query = select(UploadedArtifact).order_by(UploadedArtifact.created_at.desc())
    if workflow_id:
        query = query.where(UploadedArtifact.workflow_id == workflow_id)
    if kind:
        query = query.where(UploadedArtifact.kind == kind)
    rows = list(session.exec(query))
    return [
        ArtifactRead(
            id=row.id,
            workflow_id=row.workflow_id,
            kind=row.kind,
            file_name=row.file_name,
            file_size=row.file_size,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/artifacts/{artifact_id}/download")
def download_artifact(artifact_id: str, session: Session = Depends(get_session)):
    row = session.get(UploadedArtifact, artifact_id)
    if not row:
        raise HTTPException(status_code=404, detail="artifact not found")
    path = Path(row.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="artifact file missing")
    return FileResponse(path, filename=row.file_name)
