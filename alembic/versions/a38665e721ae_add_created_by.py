"""add_created_by

Revision ID: a38665e721ae
Revises: cd0f621d3632
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = 'a38665e721ae'
down_revision = 'cd0f621d3632'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('agents', sa.Column('created_by', sa.BigInteger(), nullable=True))
    op.create_index('ix_agents_created_by', 'agents', ['created_by'])
    op.add_column('knowledge_bases', sa.Column('created_by', sa.BigInteger(), nullable=True))
    op.create_index('ix_knowledge_bases_created_by', 'knowledge_bases', ['created_by'])
    op.add_column('workflows', sa.Column('created_by', sa.BigInteger(), nullable=True))
    op.create_index('ix_workflows_created_by', 'workflows', ['created_by'])


def downgrade() -> None:
    op.drop_index('ix_workflows_created_by', table_name='workflows')
    op.drop_column('workflows', 'created_by')
    op.drop_index('ix_knowledge_bases_created_by', table_name='knowledge_bases')
    op.drop_column('knowledge_bases', 'created_by')
    op.drop_index('ix_agents_created_by', table_name='agents')
    op.drop_column('agents', 'created_by')
