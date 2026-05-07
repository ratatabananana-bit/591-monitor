"""initial

Revision ID: 001
Revises:
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('listings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('listing_id', sa.String(length=50), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('title', sa.String(length=300), nullable=True),
        sa.Column('price', sa.Integer(), nullable=True),
        sa.Column('district', sa.String(length=100), nullable=True),
        sa.Column('address', sa.String(length=300), nullable=True),
        sa.Column('size_ping', sa.Float(), nullable=True),
        sa.Column('room_type', sa.String(length=50), nullable=True),
        sa.Column('floor', sa.String(length=50), nullable=True),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lng', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('score', sa.Float(), nullable=True),
        sa.Column('missing_count', sa.Integer(), nullable=False),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('listing_id')
    )
    op.create_index('ix_listings_listing_id', 'listings', ['listing_id'])
    op.create_index('ix_listings_status', 'listings', ['status'])

    op.create_table('search_profiles',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('city', sa.String(length=50), nullable=False),
        sa.Column('districts', sa.JSON(), nullable=False),
        sa.Column('price_min', sa.Integer(), nullable=True),
        sa.Column('price_max', sa.Integer(), nullable=True),
        sa.Column('room_types', sa.JSON(), nullable=False),
        sa.Column('required_keywords', sa.JSON(), nullable=False),
        sa.Column('rejected_keywords', sa.JSON(), nullable=False),
        sa.Column('scan_interval_minutes', sa.Integer(), nullable=False),
        sa.Column('last_scanned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('commute_anchors',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('address', sa.String(length=300), nullable=False),
        sa.Column('lat', sa.Float(), nullable=True),
        sa.Column('lng', sa.Float(), nullable=True),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('listing_events',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('listing_id', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('old_value', sa.JSON(), nullable=True),
        sa.Column('new_value', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_listing_events_listing_id', 'listing_events', ['listing_id'])

    op.create_table('scan_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('profile_id', sa.Uuid(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('listings_found', sa.Integer(), nullable=False),
        sa.Column('new_listings', sa.Integer(), nullable=False),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['search_profiles.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scan_runs_profile_id', 'scan_runs', ['profile_id'])

    op.create_table('commute_results',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('listing_id', sa.Uuid(), nullable=False),
        sa.Column('anchor_id', sa.Uuid(), nullable=False),
        sa.Column('walk_minutes', sa.Integer(), nullable=True),
        sa.Column('transit_minutes', sa.Integer(), nullable=True),
        sa.Column('distance_meters', sa.Integer(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['anchor_id'], ['commute_anchors.id']),
        sa.ForeignKeyConstraint(['listing_id'], ['listings.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('listing_id', 'anchor_id')
    )
    op.create_index('ix_commute_results_listing_id', 'commute_results', ['listing_id'])
    op.create_index('ix_commute_results_anchor_id', 'commute_results', ['anchor_id'])


def downgrade() -> None:
    op.drop_table('commute_results')
    op.drop_table('scan_runs')
    op.drop_table('listing_events')
    op.drop_table('commute_anchors')
    op.drop_table('search_profiles')
    op.drop_table('listings')
