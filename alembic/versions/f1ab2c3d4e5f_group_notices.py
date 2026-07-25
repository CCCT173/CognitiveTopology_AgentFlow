"""group notices (公告/通知) + read tracking

Revision ID: f1ab2c3d4e5f
Revises: e9fa0b1c2d3e
Create Date: 2026-07-20 16:35:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f1ab2c3d4e5f'
down_revision = 'e9fa0b1c2d3e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'group_notices',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('group_id', sa.BigInteger(), sa.ForeignKey('work_groups.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('author_id', sa.BigInteger(), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False, server_default=''),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('pinned', sa.Boolean(), nullable=False, server_default=sa.text('0'), index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP'), index=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_table(
        'group_notice_reads',
        sa.Column('notice_id', sa.BigInteger(), sa.ForeignKey('group_notices.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True),
        sa.Column('read_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    op.drop_table('group_notice_reads')
    op.drop_table('group_notices')
