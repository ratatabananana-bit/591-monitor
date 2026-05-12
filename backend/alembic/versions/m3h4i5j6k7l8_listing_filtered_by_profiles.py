"""listing filtered_by_profiles column

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-05-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'm3h4i5j6k7l8'
down_revision = 'l2g3h4i5j6k7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('listings', sa.Column('filtered_by_profiles', sa.JSON(), nullable=True))
    # Populate filtered_by_profiles for existing FILTERED listings
    # using their matched_profiles (they were found by those profiles but failed keyword check)
    op.execute("""
        UPDATE listings
        SET filtered_by_profiles = matched_profiles
        WHERE status = 'FILTERED'
          AND matched_profiles IS NOT NULL
          AND matched_profiles::text <> '[]'
    """)
    # Default empty array for all others
    op.execute("""
        UPDATE listings
        SET filtered_by_profiles = '[]'::json
        WHERE filtered_by_profiles IS NULL
    """)


def downgrade():
    op.drop_column('listings', 'filtered_by_profiles')
