"""chat_threads

Revision ID: a5ad17bc9a44
Revises: a38665e721ae
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = 'a5ad17bc9a44'
down_revision = 'a38665e721ae'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'chat_threads',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('thread_id', sa.String(64), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('agent_name', sa.String(64), nullable=False),
        sa.Column('title', sa.String(128), server_default='新对话'),
        sa.Column('last_message', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_chat_threads_thread_id', 'chat_threads', ['thread_id'], unique=True)
    op.create_index('ix_chat_threads_user_id', 'chat_threads', ['user_id'])
    op.create_index('ix_chat_threads_agent_name', 'chat_threads', ['agent_name'])

    op.add_column('agent_messages', sa.Column('user_id', sa.BigInteger(), server_default='0', nullable=False))
    op.create_index('ix_agent_messages_user_id', 'agent_messages', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_agent_messages_user_id', table_name='agent_messages')
    op.drop_column('agent_messages', 'user_id')
    op.drop_index('ix_chat_threads_agent_name', table_name='chat_threads')
    op.drop_index('ix_chat_threads_user_id', table_name='chat_threads')
    op.drop_index('ix_chat_threads_thread_id', table_name='chat_threads')
    op.drop_table('chat_threads')
