"""listing matched_profiles

Revision ID: e5f6a7b8c9d0
Revises: d1e2f3a4b5c6
Create Date: 2026-05-07

"""
from alembic import op
import sqlalchemy as sa

revision = 'e5f6a7b8c9d0'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('matched_profiles', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('listings', 'matched_profiles')
