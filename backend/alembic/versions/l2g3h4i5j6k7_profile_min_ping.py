"""search_profile min_ping column

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'l2g3h4i5j6k7'
down_revision = 'k1f2g3h4i5j6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('search_profiles', sa.Column('min_ping', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('search_profiles', 'min_ping')
