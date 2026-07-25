"""workflow_run composite indexes

Revision ID: c1d2e3f4a5b6
Revises: b7c8f9a1e2d3
Create Date: 2026-07-20
"""
from alembic import op
import sqlalchemy as sa


revision = 'c1d2e3f4a5b6'
down_revision = 'b7c8f9a1e2d3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 复合索引: workflow_id + created_at, 用于 "某工作流最近运行" 查询
    op.create_index('ix_wf_runs_wf_created', 'workflow_runs', ['workflow_id', 'created_at'])
    # 状态单列索引, 用于 Dashboard 成功率统计
    op.create_index('ix_wf_runs_status', 'workflow_runs', ['status'])


def downgrade() -> None:
    op.drop_index('ix_wf_runs_status', table_name='workflow_runs')
    op.drop_index('ix_wf_runs_wf_created', table_name='workflow_runs')
