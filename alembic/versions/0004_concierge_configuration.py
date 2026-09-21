"""concierge_configuration + guide_publications (publish pipeline)

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-18

Schema only. Seed data lives in app/configuration_store.py because
app/db.py's create_all() -- not Alembic -- is the real runtime path.
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "concierge_configuration",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("organization_id", sa.String, nullable=False),
        sa.Column("business_profile", sa.JSON, nullable=False),
        sa.Column("identity", sa.JSON, nullable=False),
        sa.Column("terminology", sa.JSON, nullable=False),
        sa.Column("has_unpublished_changes", sa.Boolean, nullable=False),
        sa.Column("last_published_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_concierge_configuration_organization_id",
        "concierge_configuration",
        ["organization_id"],
        unique=True,
    )
    op.create_table(
        "guide_publications",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("organization_id", sa.String, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("published_by", sa.String, nullable=False),
        sa.Column("content_hash", sa.String, nullable=False),
        sa.Column("instructions_text", sa.Text, nullable=False),
        sa.Column("published_config", sa.JSON, nullable=False),
        sa.Column("knowledge_item_count", sa.Integer, nullable=False),
        sa.Column("bundle_bytes", sa.LargeBinary, nullable=True),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("warnings", sa.JSON, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_guide_publications_organization_id", "guide_publications",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_guide_publications_organization_id", table_name="guide_publications")
    op.drop_table("guide_publications")
    op.drop_index(
        "ix_concierge_configuration_organization_id",
        table_name="concierge_configuration",
    )
    op.drop_table("concierge_configuration")
