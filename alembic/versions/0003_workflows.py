"""workflows: console-managed workflows (E6 slice 3)

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-17

"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("organization_id", sa.String, nullable=False),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("steps", sa.JSON, nullable=False),
        sa.Column("execution_count", sa.Integer, nullable=False),
        sa.Column("last_updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_workflows_organization_id", "workflows", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_workflows_organization_id", table_name="workflows")
    op.drop_table("workflows")
