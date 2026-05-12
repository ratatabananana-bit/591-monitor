"""scan_runs stats columns

Revision ID: d1e2f3a4b5c6
Revises: c4d8e9f1a023
Create Date: 2026-05-07

"""
from alembic import op
import sqlalchemy as sa

revision = 'd1e2f3a4b5c6'
down_revision = 'c4d8e9f1a023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('scan_runs', sa.Column('profile_name', sa.String(100), nullable=True))
    op.add_column('scan_runs', sa.Column('updated_listings', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('scan_runs', sa.Column('gone_listings', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('scan_runs', 'gone_listings')
    op.drop_column('scan_runs', 'updated_listings')
    op.drop_column('scan_runs', 'profile_name')
