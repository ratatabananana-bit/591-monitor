"""listing score_breakdown column

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-05-08
"""
from alembic import op
import sqlalchemy as sa

revision = 'k1f2g3h4i5j6'
down_revision = 'j0e1f2g3h4i5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('listings', sa.Column('score_breakdown', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('listings', 'score_breakdown')
