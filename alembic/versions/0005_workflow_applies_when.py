"""workflows.applies_when

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-11
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflows", sa.Column("applies_when", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("workflows", "applies_when")
