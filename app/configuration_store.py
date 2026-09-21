"""SQLAlchemy-backed access to the single console configuration row.
Called by app/concierge_api.py and app/guide_publish/publisher.py. Same
conventions as app/workflow_store.py: every function takes a Session and
none commit, so the caller owns the transaction boundary.

Unlike the other console stores this one seeds itself. app/db.py's
create_all() is the real runtime schema path, so a migration's data step
would never run for most checkouts -- the row is created on first read
instead, from the app/config.py defaults.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import config, models

# The only keys a PATCH may carry. Tenancy and publishing markers are set by
# this module, never by a caller -- mirroring the frontend's
# ConciergeConfigurationPatch, which is Pick<..., these three>.
EDITABLE_SECTIONS = frozenset({"business_profile", "identity", "terminology"})


def get_configuration(db: Session) -> models.ConciergeConfiguration:
    """Returns the organization's configuration, creating it from the
    app/config.py defaults on first call."""
    row = db.scalar(
        select(models.ConciergeConfiguration).where(
            models.ConciergeConfiguration.organization_id
            == config.DEFAULT_ORGANIZATION_ID
        )
    )
    if row is None:
        row = models.ConciergeConfiguration(
            organization_id=config.DEFAULT_ORGANIZATION_ID,
            business_profile=dict(config.DEFAULT_BUSINESS_PROFILE),
            identity=dict(config.DEFAULT_IDENTITY),
            terminology=dict(config.DEFAULT_TERMINOLOGY),
            has_unpublished_changes=False,
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        db.flush()
    return row


def save_draft(
    db: Session, row: models.ConciergeConfiguration, patch: dict[str, Any]
) -> models.ConciergeConfiguration:
    """Applies only the sections present in `patch`. Each one replaces that
    column wholesale -- never a field-by-field merge -- so a caller sending
    `identity` alone leaves `business_profile` untouched."""
    unknown = set(patch) - EDITABLE_SECTIONS
    if unknown:
        raise ValueError(f"unknown configuration section: {', '.join(sorted(unknown))}")
    for section, value in patch.items():
        setattr(row, section, value)
    row.has_unpublished_changes = True
    row.updated_at = datetime.utcnow()
    db.flush()
    return row


def mark_published(
    db: Session, row: models.ConciergeConfiguration, published_at: datetime
) -> models.ConciergeConfiguration:
    """Called ONLY after a confirmed successful push. A failed publish must
    leave has_unpublished_changes set, so the console never looks published
    when the live guide was not updated."""
    row.has_unpublished_changes = False
    row.last_published_at = published_at
    row.updated_at = datetime.utcnow()
    db.flush()
    return row
