"""GET/POST /api/workflows, GET/PATCH/DELETE /api/workflows/{id},
POST /api/workflows/{id}/publish -- frontend/src/services/
workflowService.ts's httpWorkflowService, made real (E6 slice 3).

These records drive the admin console's Workflows pages. Publishing a
workflow here only marks the row; it does not touch the guide. Active
workflows with an "Applies when" reach live calls through Guide Publish
(app/guide/publish/render.py workflow_prose), which renders them into the
guide's instructions as prose -- the guide follows the steps, this app does
not enforce them, and execution_count stays 0. See docs/superpowers/specs/
2026-11-11-workflows-in-guide-instructions-design.md.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator
from sqlalchemy.orm import Session

from app import models
from app.console.auth import sessions as auth
from app.db import get_db

from . import store as workflow_store
from .tools import WORKFLOW_TOOLS

router = APIRouter()

WorkflowStatus = Literal["draft", "active", "inactive"]
WorkflowStepType = Literal[
    "ask_customer", "validate", "look_up", "make_decision", "execute_action",
    "confirm", "send_communication", "escalate", "end",
]
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


_LEGACY_STEP_KEYS = frozenset({"requiredIntegrationId", "configuration"})


class WorkflowStepModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: NonBlankStr
    name: NonBlankStr
    description: str | None = None
    type: WorkflowStepType
    tool: str | None = None
    errorBehavior: str | None = None
    escalationBehavior: str | None = None

    @field_validator("tool")
    @classmethod
    def _tool_must_be_a_guide_tool(cls, value: str | None) -> str | None:
        if value is not None and value not in WORKFLOW_TOOLS:
            raise ValueError(f"unknown tool {value!r}; expected one of {', '.join(WORKFLOW_TOOLS)}")
        return value


class WorkflowOut(BaseModel):
    id: str
    organizationId: str
    name: str
    description: str | None = None
    appliesWhen: str | None = None
    status: WorkflowStatus
    version: int
    steps: list[WorkflowStepModel]
    executionCount: int
    lastUpdatedAt: str


class CreateWorkflowIn(BaseModel):
    name: NonBlankStr
    description: str | None = None
    appliesWhen: str | None = None


class WorkflowPatchIn(BaseModel):
    name: NonBlankStr | None = None
    description: str | None = None
    appliesWhen: str | None = None
    steps: list[WorkflowStepModel] | None = None

    @model_validator(mode="after")
    def _required_columns_cannot_be_null(self) -> "WorkflowPatchIn":
        # Absent means "leave alone"; an explicit null would either violate a
        # NOT NULL column (name) or silently wipe the array (steps).
        for field in ("name", "steps"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


def _to_iso(value: datetime | None) -> str | None:
    return value.isoformat() + "Z" if value else None


def _workflow_out(workflow: models.Workflow) -> WorkflowOut:
    return WorkflowOut(
        id=workflow.id,
        organizationId=workflow.organization_id,
        name=workflow.name,
        description=workflow.description,
        appliesWhen=workflow.applies_when,
        status=workflow.status,
        version=workflow.version,
        # Steps saved before `tool` replaced requiredIntegrationId, or before
        # the per-step `configuration` map was removed, still carry those keys
        # (extra="forbid" would reject them); drop them on read, the next save
        # writes the clean shape.
        steps=[
            WorkflowStepModel(**{k: v for k, v in step.items() if k not in _LEGACY_STEP_KEYS})
            for step in (workflow.steps or [])
        ],
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
    workflow = workflow_store.create_workflow(
        db,
        name=payload.name,
        description=payload.description,
        applies_when=payload.appliesWhen,
    )
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
    # name/description/steps share spelling with the model's attributes, so
    # model_dump() yields what save_draft expects (steps' camelCase keys are
    # stored verbatim in the JSON column). appliesWhen is the exception: it
    # maps to applies_when, and an explicit null clears it.
    patch: dict[str, Any] = payload.model_dump(exclude_unset=True)
    if "appliesWhen" in patch:
        patch["applies_when"] = patch.pop("appliesWhen")
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
