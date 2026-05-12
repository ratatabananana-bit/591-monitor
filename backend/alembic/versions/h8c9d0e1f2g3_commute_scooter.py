"""commute scooter columns

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa

revision = 'h8c9d0e1f2g3'
down_revision = 'g7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('commute_results', sa.Column('scooter_minutes', sa.Integer(), nullable=True))
    op.add_column('commute_results', sa.Column('scooter_distance_meters', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('commute_results', 'scooter_distance_meters')
    op.drop_column('commute_results', 'scooter_minutes')
