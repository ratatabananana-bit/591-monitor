"""listing facilities column

Revision ID: n4i5j6k7l8m9
Revises: m3h4i5j6k7l8
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa

revision = 'n4i5j6k7l8m9'
down_revision = 'm3h4i5j6k7l8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('listings', sa.Column('facilities', sa.JSON(), nullable=True))
    op.execute("UPDATE listings SET facilities = '[]'::json WHERE facilities IS NULL")


def downgrade():
    op.drop_column('listings', 'facilities')
