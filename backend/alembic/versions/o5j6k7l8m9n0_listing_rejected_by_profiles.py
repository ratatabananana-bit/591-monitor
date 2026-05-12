"""listing rejected_by_profiles column

Revision ID: o5j6k7l8m9n0
Revises: n4i5j6k7l8m9
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa

revision = 'o5j6k7l8m9n0'
down_revision = 'n4i5j6k7l8m9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('listings', sa.Column('rejected_by_profiles', sa.JSON(), nullable=True))
    op.execute("UPDATE listings SET rejected_by_profiles = '[]'::json WHERE rejected_by_profiles IS NULL")


def downgrade():
    op.drop_column('listings', 'rejected_by_profiles')
