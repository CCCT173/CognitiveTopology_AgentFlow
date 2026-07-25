"""phase_9_collab_and_keys

Revision ID: f9a0b1c2d3e4
Revises: 3a2b1c0d9e8f
Create Date: 2026-07-23

Phase 4-9 新增表/字段：
- refresh_tokens (JWT refresh token)
- hitl (PendingConfirmation HITL)
- workflow_permissions (工作流共享)
- workflow_api_keys (工作流 API Key)
- workflows.version (乐观锁版本号)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "f9a0b1c2d3e4"
down_revision = "3a2b1c0d9e8f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. workflows.version 乐观锁
    op.add_column("workflows", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    # 2. refresh_tokens
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, index=True),
        sa.Column("token_hash", sa.String(128), unique=True, index=True, nullable=False),
        sa.Column("device", sa.String(200), nullable=True, server_default=""),
        sa.Column("ip", sa.String(64), nullable=True, server_default=""),
        sa.Column("user_agent", sa.String(500), nullable=True, server_default=""),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("replaced_by", sa.String(128), nullable=True, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # 3. pending_confirmations (HITL)
    op.create_table(
        "pending_confirmations",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, index=True),
        sa.Column("thread_id", sa.String(64), nullable=True, server_default=""),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("args_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("risk_level", sa.String(16), nullable=False, server_default="high"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("denied_at", sa.DateTime(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # 4. workflow_permissions
    op.create_table(
        "workflow_permissions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, index=True),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, index=True),
        sa.Column("role", sa.String(16), nullable=False, server_default="viewer"),
        sa.Column("granted_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workflow_id", "user_id", name="uq_wf_perm_user"),
    )

    # 5. workflow_api_keys
    op.create_table(
        "workflow_api_keys",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("workflow_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, index=True),
        sa.Column("name", sa.String(64), nullable=False, server_default="default"),
        sa.Column("api_key_hash", sa.String(64), unique=True, index=True, nullable=False),
        sa.Column("api_key", sa.String(64), nullable=True, server_default=""),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("calls_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_ip", sa.String(64), nullable=True, server_default=""),
        sa.Column("created_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("workflow_id", "name", name="uq_wf_key_name"),
    )


def downgrade() -> None:
    op.drop_table("workflow_api_keys")
    op.drop_table("workflow_permissions")
    op.drop_table("pending_confirmations")
    op.drop_table("refresh_tokens")
    op.drop_column("workflows", "version")
