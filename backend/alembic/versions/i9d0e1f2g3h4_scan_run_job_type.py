"""scan_run job_type column

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-05-08

"""
from alembic import op
import sqlalchemy as sa

revision = 'i9d0e1f2g3h4'
down_revision = 'h8c9d0e1f2g3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('scan_runs', sa.Column('job_type', sa.String(30), nullable=True, server_default='scan'))


def downgrade() -> None:
    op.drop_column('scan_runs', 'job_type')
