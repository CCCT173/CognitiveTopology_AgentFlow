"""group shared workflows and skills

Revision ID: a2bc3d4e5f60
Revises: f1ab2c3d4e5f
Create Date: 2026-07-20 16:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a2bc3d4e5f60'
down_revision = 'f1ab2c3d4e5f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'group_workflows',
        sa.Column('group_id', sa.BigInteger(), sa.ForeignKey('work_groups.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('workflow_id', sa.BigInteger(), sa.ForeignKey('workflows.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('shared_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_table(
        'group_skills',
        sa.Column('group_id', sa.BigInteger(), sa.ForeignKey('work_groups.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('skill_id', sa.BigInteger(), sa.ForeignKey('skills.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('shared_by', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    op.drop_table('group_skills')
    op.drop_table('group_workflows')
