"""add_system_config_table

Revision ID: a1b2c3d4e5f6
Revises: f9a0b1c2d3e4
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "a1b2c3d4e5f6"
down_revision = "f9a0b1c2d3e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_config",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(64), unique=True, index=True, nullable=False, comment="配置键"),
        sa.Column("value", sa.Text(), nullable=False, comment="配置值"),
        sa.Column("description", sa.String(256), nullable=True, comment="配置说明"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True, comment="最后修改人"),
    )


def downgrade() -> None:
    op.drop_table("system_config")
