"""SQLAlchemy-backed CRUD for console workflows (E6 slice 3). Called only
by app/workflow_api.py. Same conventions as app/knowledge_store.py: every
function takes a Session and none commit, so the caller owns the
transaction boundary.

Console-only: publishing a workflow here has no effect on live calls --
nothing in app/'s call-handling code reads this table. See
docs/superpowers/specs/2026-09-17-e6-workflows-design.md, "Future".
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config, models


def _scoped():
    return select(models.Workflow).where(
        models.Workflow.organization_id == config.DEFAULT_ORGANIZATION_ID
    )


def list_workflows(db: Session) -> list[models.Workflow]:
    """Most recently updated first, matching the mock service's
    sortByDesc(lastUpdatedAt). No filters, no pagination -- matches
    WorkflowService.list(): Promise<Workflow[]> exactly."""
    return list(db.scalars(_scoped().order_by(models.Workflow.last_updated_at.desc())))


def get_workflow(db: Session, workflow_id: str) -> models.Workflow | None:
    return db.scalar(_scoped().where(models.Workflow.id == workflow_id))


def create_workflow(
    db: Session, *, name: str, description: str | None = None
) -> models.Workflow:
    workflow = models.Workflow(
        organization_id=config.DEFAULT_ORGANIZATION_ID,
        name=name,
        description=description,
        status="draft",
        version=1,
        steps=[],
        execution_count=0,
        last_updated_at=datetime.utcnow(),
    )
    db.add(workflow)
    db.flush()
    return workflow


def save_draft(
    db: Session, workflow: models.Workflow, patch: dict[str, Any]
) -> models.Workflow:
    """Applies only the keys present in `patch` -- name/description/steps.
    `steps`, when present, replaces the entire column value wholesale; this
    is never a per-step merge. status/version are never touched here --
    the API layer (app/workflow_api.py) never puts them in a patch dict."""
    for key, value in patch.items():
        setattr(workflow, key, value)
    workflow.last_updated_at = datetime.utcnow()
    db.flush()
    return workflow


def publish_workflow(db: Session, workflow: models.Workflow) -> models.Workflow:
    if not workflow.steps:
        raise ValueError("cannot publish a workflow with no steps")
    workflow.status = "active"
    workflow.version += 1
    workflow.last_updated_at = datetime.utcnow()
    db.flush()
    return workflow


def delete_workflow(db: Session, workflow: models.Workflow) -> None:
    db.delete(workflow)
    db.flush()
