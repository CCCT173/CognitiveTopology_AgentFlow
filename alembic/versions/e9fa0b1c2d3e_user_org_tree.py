"""users add manager_id + department for org tree

Revision ID: e9fa0b1c2d3e
Revises: d8e9f0a1b2c3
Create Date: 2026-07-20 16:22:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e9fa0b1c2d3e'
down_revision = 'd8e9f0a1b2c3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('department', sa.String(length=64), nullable=False, server_default='', comment='所属部门'))
    op.add_column('users', sa.Column('manager_id', sa.BigInteger(), nullable=True, comment='直属上级用户ID'))
    op.create_index('ix_users_manager_id', 'users', ['manager_id'])
    # 外键: manager_id → users.user_id (SET NULL on delete 避免级联删除风险)
    op.create_foreign_key('fk_users_manager_id', 'users', 'users', ['manager_id'], ['user_id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_users_manager_id', 'users', type_='foreignkey')
    op.drop_index('ix_users_manager_id', table_name='users')
    op.drop_column('users', 'manager_id')
    op.drop_column('users', 'department')
