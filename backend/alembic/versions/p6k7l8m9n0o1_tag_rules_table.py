"""add tag_rules table and listing.tags column

Revision ID: p6k7l8m9n0o1
Revises: o5j6k7l8m9n0
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa

revision = 'p6k7l8m9n0o1'
down_revision = 'o5j6k7l8m9n0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tag_rules',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('keywords', sa.JSON(), nullable=True),
        sa.Column('reject_keywords', sa.JSON(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.add_column('listings', sa.Column('tags', sa.JSON(), nullable=True))
    op.execute("UPDATE listings SET tags = '[]'::json WHERE tags IS NULL")


def downgrade():
    op.drop_column('listings', 'tags')
    op.drop_table('tag_rules')
