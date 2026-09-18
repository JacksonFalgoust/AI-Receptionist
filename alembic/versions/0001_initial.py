"""initial schema: conversations, conversation_messages, conversation_actions, auth_sessions

Revision ID: 0001
Revises:
Create Date: 2026-09-14

"""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("organization_id", sa.String, nullable=False),
        sa.Column("customer_name", sa.String, nullable=True),
        sa.Column("customer_phone", sa.String, nullable=True),
        sa.Column("channel", sa.String, nullable=False),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("ended_at", sa.DateTime, nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("intent", sa.String, nullable=True),
        sa.Column("outcome", sa.String, nullable=False),
        sa.Column("escalated", sa.Boolean, nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("assigned_employee", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_conversations_organization_id", "conversations", ["organization_id"])

    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("conversation_id", sa.String, sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("speaker", sa.String, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("at", sa.DateTime, nullable=False),
    )
    op.create_index(
        "ix_conversation_messages_conversation_id", "conversation_messages", ["conversation_id"]
    )

    op.create_table(
        "conversation_actions",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("conversation_id", sa.String, sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("system", sa.String, nullable=False),
        sa.Column("at", sa.DateTime, nullable=False),
        sa.Column("result", sa.Text, nullable=False),
        sa.Column("status", sa.String, nullable=False),
        sa.Column("details", sa.JSON, nullable=True),
    )
    op.create_index(
        "ix_conversation_actions_conversation_id", "conversation_actions", ["conversation_id"]
    )

    op.create_table(
        "auth_sessions",
        sa.Column("token", sa.String, primary_key=True),
        sa.Column("user_email", sa.String, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("auth_sessions")
    op.drop_index("ix_conversation_actions_conversation_id", table_name="conversation_actions")
    op.drop_table("conversation_actions")
    op.drop_index("ix_conversation_messages_conversation_id", table_name="conversation_messages")
    op.drop_table("conversation_messages")
    op.drop_index("ix_conversations_organization_id", table_name="conversations")
    op.drop_table("conversations")
