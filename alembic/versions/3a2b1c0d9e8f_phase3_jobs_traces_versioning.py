"""phase3: jobs/traces/versioning tables

Revision ID: 3a2b1c0d9e8f
Revises: a2bc3d4e5f60
Create Date: 2026-07-23
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql, sqlite

revision: str = '3a2b1c0d9e8f'
down_revision: Union[str, Sequence[str], None] = 'a2bc3d4e5f60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _bigint():
    """跨数据库主键类型"""
    return sa.BigInteger().with_variant(sa.Integer(), 'sqlite')


def upgrade() -> None:
    # jobs
    op.create_table(
        'jobs',
        sa.Column('id', _bigint(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(128), nullable=False, index=True),
        sa.Column('params_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending', index=True),
        sa.Column('result_json', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('locked_by', sa.String(64), nullable=True),
        sa.Column('heartbeat_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_jobs_status_created', 'jobs', ['status', 'created_at'])

    # traces
    op.create_table(
        'traces',
        sa.Column('id', _bigint(), primary_key=True, autoincrement=True),
        sa.Column('trace_id', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('kind', sa.String(32), nullable=False, index=True),
        sa.Column('user_id', _bigint(), nullable=False, server_default='0', index=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='running', index=True),
        sa.Column('target_id', _bigint(), nullable=True, index=True),
        sa.Column('input_summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('output_summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
    )

    # spans
    op.create_table(
        'spans',
        sa.Column('id', _bigint(), primary_key=True, autoincrement=True),
        sa.Column('span_id', sa.String(64), nullable=False, unique=True, index=True),
        sa.Column('trace_id', sa.String(64), nullable=False, index=True),
        sa.Column('parent_span_id', sa.String(64), nullable=True, index=True),
        sa.Column('kind', sa.String(32), nullable=False, index=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(16), nullable=False, server_default='running'),
        sa.Column('input_summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('output_summary', sa.Text(), nullable=False, server_default=''),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('tokens_in', sa.Integer(), nullable=True),
        sa.Column('tokens_out', sa.Integer(), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['trace_id'], ['traces.trace_id']),
    )
    op.create_index('ix_spans_trace_kind', 'spans', ['trace_id', 'kind'])

    # activity_logs
    op.create_table(
        'activity_logs',
        sa.Column('id', _bigint(), primary_key=True, autoincrement=True),
        sa.Column('entity_type', sa.String(32), nullable=False, index=True),
        sa.Column('entity_id', _bigint(), nullable=False, index=True),
        sa.Column('action', sa.String(32), nullable=False, index=True),
        sa.Column('user_id', _bigint(), nullable=False, server_default='0', index=True),
        sa.Column('before_json', sa.Text(), nullable=False, server_default=''),
        sa.Column('after_json', sa.Text(), nullable=False, server_default=''),
        sa.Column('meta_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, index=True),
    )

    # workflow_versions
    op.create_table(
        'workflow_versions',
        sa.Column('id', _bigint(), primary_key=True, autoincrement=True),
        sa.Column('workflow_id', _bigint(), nullable=False, index=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('definition_json', sa.Text(), nullable=False),
        sa.Column('changelog', sa.Text(), nullable=False, server_default=''),
        sa.Column('published_by', _bigint(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
    )

    # agent_versions
    op.create_table(
        'agent_versions',
        sa.Column('id', _bigint(), primary_key=True, autoincrement=True),
        sa.Column('agent_id', _bigint(), nullable=False, index=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=False, server_default=''),
        sa.Column('config_json', sa.Text(), nullable=False),
        sa.Column('changelog', sa.Text(), nullable=False, server_default=''),
        sa.Column('published_by', _bigint(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
    )


def downgrade() -> None:
    op.drop_table('agent_versions')
    op.drop_table('workflow_versions')
    op.drop_table('activity_logs')
    op.drop_table('spans')
    op.drop_table('traces')
    op.drop_table('jobs')
