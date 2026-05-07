"""scan_runs profile_id ON DELETE SET NULL

Revision ID: b12e3f4a8c01
Revises: 001
Create Date: 2026-05-07
"""
from alembic import op

revision = 'b12e3f4a8c01'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old FK, re-add with ON DELETE SET NULL
    op.drop_constraint('scan_runs_profile_id_fkey', 'scan_runs', type_='foreignkey')
    op.create_foreign_key(
        'scan_runs_profile_id_fkey',
        'scan_runs', 'search_profiles',
        ['profile_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('scan_runs_profile_id_fkey', 'scan_runs', type_='foreignkey')
    op.create_foreign_key(
        'scan_runs_profile_id_fkey',
        'scan_runs', 'search_profiles',
        ['profile_id'], ['id'],
    )
