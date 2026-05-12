"""add telegram_subscriptions and telegram_alerted_listings tables

Revision ID: q7l8m9n0o1p2
Revises: p6k7l8m9n0o1
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa

revision = 'q7l8m9n0o1p2'
down_revision = 'p6k7l8m9n0o1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'telegram_subscriptions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('chat_id', sa.String(50), nullable=False, unique=True),
        sa.Column('chat_name', sa.String(200), nullable=True),
        sa.Column('subscribed_tags', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'telegram_alerted_listings',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('subscription_id', sa.UUID(), nullable=False),
        sa.Column('listing_id', sa.UUID(), nullable=False),
        sa.Column('alerted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('alert_type', sa.String(30), nullable=False, server_default='new'),
        sa.ForeignKeyConstraint(['subscription_id'], ['telegram_subscriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('subscription_id', 'listing_id', name='uq_sub_listing'),
    )


def downgrade():
    op.drop_table('telegram_alerted_listings')
    op.drop_table('telegram_subscriptions')
