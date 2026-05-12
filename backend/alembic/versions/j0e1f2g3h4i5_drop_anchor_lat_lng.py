"""drop anchor lat lng

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa

revision = 'j0e1f2g3h4i5'
down_revision = 'i9d0e1f2g3h4'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('commute_anchors', 'lat')
    op.drop_column('commute_anchors', 'lng')


def downgrade():
    op.add_column('commute_anchors', sa.Column('lat', sa.Float(), nullable=True))
    op.add_column('commute_anchors', sa.Column('lng', sa.Float(), nullable=True))
