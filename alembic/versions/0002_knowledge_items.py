"""knowledge_items: console-managed knowledge (E6 slice 2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-16

"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("organization_id", sa.String, nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("category", sa.String, nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("tags", sa.JSON, nullable=False),
        sa.Column("effective_date", sa.DateTime, nullable=True),
        sa.Column("expiration_date", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_knowledge_items_organization_id", "knowledge_items", ["organization_id"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_items_organization_id", table_name="knowledge_items")
    op.drop_table("knowledge_items")
