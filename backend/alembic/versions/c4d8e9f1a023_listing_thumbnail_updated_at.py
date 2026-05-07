"""listing thumbnail_url and listing_updated_at columns

Revision ID: c4d8e9f1a023
Revises: b12e3f4a8c01
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d8e9f1a023'
down_revision = 'b12e3f4a8c01'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('listings', sa.Column('thumbnail_url', sa.String(500), nullable=True))
    op.add_column('listings', sa.Column('listing_updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('listings', 'listing_updated_at')
    op.drop_column('listings', 'thumbnail_url')
