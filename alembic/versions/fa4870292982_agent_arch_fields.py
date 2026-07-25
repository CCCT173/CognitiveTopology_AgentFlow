"""agent_arch_fields

Revision ID: fa4870292982
Revises: a5ad17bc9a44
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = 'fa4870292982'
down_revision = 'a5ad17bc9a44'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('agents', sa.Column('workflow_id', sa.BigInteger(), nullable=True))
    op.add_column('agents', sa.Column('parent_agent_id', sa.BigInteger(), nullable=True))
    op.add_column('agents', sa.Column('max_iterations', sa.BigInteger(), server_default='10', nullable=False))
    op.add_column('agent_messages', sa.Column('tool_call', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('agent_messages', 'tool_call')
    op.drop_column('agents', 'max_iterations')
    op.drop_column('agents', 'parent_agent_id')
    op.drop_column('agents', 'workflow_id')
