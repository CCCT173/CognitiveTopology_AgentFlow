"""skill_created_by

Revision ID: b7c8f9a1e2d3
Revises: fa4870292982
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa


revision = 'b7c8f9a1e2d3'
down_revision = 'fa4870292982'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('skills', sa.Column('created_by', sa.BigInteger(), nullable=True))
    op.create_index('ix_skills_created_by', 'skills', ['created_by'])


def downgrade() -> None:
    op.drop_index('ix_skills_created_by', table_name='skills')
    op.drop_column('skills', 'created_by')
