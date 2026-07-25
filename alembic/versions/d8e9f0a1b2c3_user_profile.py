"""user profile extension (title/company/location/phone/website/bio/birthday)

Revision ID: d8e9f0a1b2c3
Revises: c1d2e3f4a5b6
Create Date: 2026-07-20 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8e9f0a1b2c3'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # MySQL 不允许 TEXT/Blob 设 default，所以先加 nullable，UPDATE 空串，再改 NOT NULL
    op.add_column('users', sa.Column('title', sa.String(length=64), nullable=False, server_default='', comment='职位/头衔'))
    op.add_column('users', sa.Column('company', sa.String(length=128), nullable=False, server_default='', comment='公司/组织'))
    op.add_column('users', sa.Column('location', sa.String(length=64), nullable=False, server_default='', comment='所在地'))
    op.add_column('users', sa.Column('phone', sa.String(length=32), nullable=False, server_default='', comment='联系电话'))
    op.add_column('users', sa.Column('website', sa.String(length=256), nullable=False, server_default='', comment='个人主页链接'))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True, comment='个人简介'))
    op.add_column('users', sa.Column('birthday', sa.Date(), nullable=True, comment='生日'))
    op.execute("UPDATE users SET bio = '' WHERE bio IS NULL")
    op.alter_column('users', 'bio', nullable=False, existing_type=sa.Text(), server_default='')


def downgrade() -> None:
    op.drop_column('users', 'birthday')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'website')
    op.drop_column('users', 'phone')
    op.drop_column('users', 'location')
    op.drop_column('users', 'company')
    op.drop_column('users', 'title')
