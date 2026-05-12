"""listing image_urls

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa

revision = 'g7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('image_urls', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('listings', 'image_urls')
