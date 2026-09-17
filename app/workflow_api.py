"""GET/POST /api/workflows, GET/PATCH/DELETE /api/workflows/{id},
POST /api/workflows/{id}/publish -- frontend/src/services/
workflowService.ts's httpWorkflowService, made real (E6 slice 3).

CONSOLE-ONLY: these records drive the admin console's Workflows pages and
nothing else. Publishing a workflow here has no effect on live calls --
nothing in app/'s call-handling code reads this table. What has to change
to close that gap: docs/superpowers/specs/
2026-09-17-e6-workflows-design.md, "Future: giving a published workflow
live effect".
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy.orm import Session

from . import auth, models, workflow_store
from .db import get_db

router = APIRouter()

WorkflowStatus = Literal["draft", "active", "inactive"]
WorkflowStepType = Literal[
    "ask_customer", "validate", "look_up", "make_decision", "execute_action",
    "confirm", "send_communication", "escalate", "end",
]
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class WorkflowStepModel(BaseModel):
    id: NonBlankStr
    name: NonBlankStr
    description: str | None = None
    type: WorkflowStepType
    requiredIntegrationId: str | None = None
    errorBehavior: str | None = None
    escalationBehavior: str | None = None
    configuration: dict[str, str] | None = None


class WorkflowOut(BaseModel):
    id: str
    organizationId: str
    name: str
    description: str | None = None
    status: WorkflowStatus
    version: int
    steps: list[WorkflowStepModel]
    executionCount: int
    lastUpdatedAt: str


class CreateWorkflowIn(BaseModel):
    name: NonBlankStr
    description: str | None = None


class WorkflowPatchIn(BaseModel):
    name: NonBlankStr | None = None
    description: str | None = None
    steps: list[WorkflowStepModel] | None = None


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def _workflow_out(workflow: models.Workflow) -> WorkflowOut:
    return WorkflowOut(
        id=workflow.id,
        organizationId=workflow.organization_id,
        name=workflow.name,
        description=workflow.description,
        status=workflow.status,
        version=workflow.version,
        steps=[WorkflowStepModel(**step) for step in (workflow.steps or [])],
        executionCount=workflow.execution_count,
        lastUpdatedAt=_to_iso(workflow.last_updated_at),
    )


def _require_workflow(db: Session, workflow_id: str) -> models.Workflow:
    workflow = workflow_store.get_workflow(db, workflow_id)
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return workflow


@router.get("/api/workflows", response_model=list[WorkflowOut])
def list_workflows(
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> list[WorkflowOut]:
    return [_workflow_out(row) for row in workflow_store.list_workflows(db)]


@router.get("/api/workflows/{workflow_id}", response_model=WorkflowOut)
def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> WorkflowOut:
    return _workflow_out(_require_workflow(db, workflow_id))


@router.post("/api/workflows", response_model=WorkflowOut, status_code=status.HTTP_201_CREATED)
def create_workflow(
    payload: CreateWorkflowIn,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> WorkflowOut:
    workflow = workflow_store.create_workflow(db, name=payload.name, description=payload.description)
    db.commit()
    return _workflow_out(workflow)


@router.patch("/api/workflows/{workflow_id}", response_model=WorkflowOut)
def update_workflow(
    workflow_id: str,
    payload: WorkflowPatchIn,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> WorkflowOut:
    workflow = _require_workflow(db, workflow_id)
    # Unlike knowledge_api.py's effectiveDate/effective_date, every field
    # here (name, description, steps) has the same spelling as the model's
    # attribute -- model_dump() already yields exactly the dict save_draft
    # expects, steps included (its camelCase keys are stored verbatim in
    # the JSON column, matching how _workflow_out reads them back out).
    patch: dict[str, Any] = payload.model_dump(exclude_unset=True)
    workflow_store.save_draft(db, workflow, patch)
    db.commit()
    return _workflow_out(workflow)


@router.post("/api/workflows/{workflow_id}/publish", response_model=WorkflowOut)
def publish_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> WorkflowOut:
    workflow = _require_workflow(db, workflow_id)
    try:
        workflow_store.publish_workflow(db, workflow)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    db.commit()
    return _workflow_out(workflow)


@router.delete("/api/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    _auth: models.AuthSession = Depends(auth.require_auth),
) -> None:
    workflow_store.delete_workflow(db, _require_workflow(db, workflow_id))
    db.commit()
