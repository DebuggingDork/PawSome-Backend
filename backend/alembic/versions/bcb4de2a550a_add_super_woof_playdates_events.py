"""add_super_woof_playdates_events

Revision ID: bcb4de2a550a
Revises: f4a9c2e1d7b6
Create Date: 2026-07-25 00:50:44.043462

Adds:
- notifications.is_super: flags a NEW_LIKE notification as a Super Woof
- playdates: real-world meetup proposals scoped to a match
- events / event_rsvps: community meetup board with RSVPs

The swipe_action / notification_type columns are plain VARCHAR (native_enum=False,
no CHECK constraint), so the new "super_like" / "playdate_*" string values need
no DDL change — see backend/app/models/swipe.py and notification.py.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'bcb4de2a550a'
down_revision: Union[str, Sequence[str], None] = 'f4a9c2e1d7b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ── notifications.is_super ──────────────────────────────────────────────
    op.add_column(
        'notifications',
        sa.Column('is_super', sa.Boolean(), nullable=False, server_default='false'),
    )

    # ── playdates ────────────────────────────────────────────────────────────
    op.create_table(
        'playdates',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'match_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('matches.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'proposed_by_pet_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('pet_profiles.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'proposed_to_pet_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('pet_profiles.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('location_name', sa.String(255), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column(
            'status',
            sa.Enum('pending', 'accepted', 'declined', 'cancelled', name='playdate_status', native_enum=False, length=20),
            nullable=False,
            server_default='pending',
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_playdates_match_id', 'playdates', ['match_id'], unique=False)
    op.create_index('ix_playdates_scheduled_at', 'playdates', ['scheduled_at'], unique=False)

    # ── events ───────────────────────────────────────────────────────────────
    op.create_table(
        'events',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'creator_user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('title', sa.String(150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('location_name', sa.String(255), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('event_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('species', sa.String(20), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_events_creator_user_id', 'events', ['creator_user_id'], unique=False)
    op.create_index('ix_events_event_time', 'events', ['event_time'], unique=False)
    op.create_index('ix_events_cancelled_at', 'events', ['cancelled_at'], unique=False)

    # ── event_rsvps ──────────────────────────────────────────────────────────
    op.create_table(
        'event_rsvps',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'event_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('events.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'pet_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('pet_profiles.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('status', sa.String(20), nullable=False, server_default='going'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )
    op.create_index('ix_event_rsvps_event_id', 'event_rsvps', ['event_id'], unique=False)
    op.create_index('ix_event_rsvps_user_id', 'event_rsvps', ['user_id'], unique=False)
    op.create_index('ix_event_rsvps_event_user', 'event_rsvps', ['event_id', 'user_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""

    # ── event_rsvps ──────────────────────────────────────────────────────────
    op.drop_index('ix_event_rsvps_event_user', table_name='event_rsvps')
    op.drop_index('ix_event_rsvps_user_id', table_name='event_rsvps')
    op.drop_index('ix_event_rsvps_event_id', table_name='event_rsvps')
    op.drop_table('event_rsvps')

    # ── events ───────────────────────────────────────────────────────────────
    op.drop_index('ix_events_cancelled_at', table_name='events')
    op.drop_index('ix_events_event_time', table_name='events')
    op.drop_index('ix_events_creator_user_id', table_name='events')
    op.drop_table('events')

    # ── playdates ────────────────────────────────────────────────────────────
    op.drop_index('ix_playdates_scheduled_at', table_name='playdates')
    op.drop_index('ix_playdates_match_id', table_name='playdates')
    op.drop_table('playdates')

    # ── notifications.is_super ──────────────────────────────────────────────
    op.drop_column('notifications', 'is_super')
