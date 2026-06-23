"""add_columns_to_existing_tables

Revision ID: e3f2a1b8c9d5
Revises: d8ed4e7ae8e4
Create Date: 2026-06-14 00:00:00.000000

Adds new columns to existing tables for:
- Swipe undo functionality (swipes.is_undone, swipes.undone_at)
- Location-based matching (users.latitude, users.longitude, users.preferred_match_radius_km)
- Pet health certifications (pet_profiles.is_vaccinated, pet_profiles.vaccination_date,
  pet_profiles.is_neutered, pet_profiles.is_trained)
- Match soft-delete (matches.deleted_at + index)
- Message soft-delete timestamp (messages.deleted_at)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3f2a1b8c9d5'
down_revision: Union[str, Sequence[str], None] = 'd8ed4e7ae8e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ── swipes ──────────────────────────────────────────────────────────────
    # Add undo-functionality columns
    op.add_column(
        'swipes',
        sa.Column(
            'is_undone',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    op.add_column(
        'swipes',
        sa.Column('undone_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Index to support time-based queries (undo window)
    op.create_index('ix_swipes_created_at', 'swipes', ['created_at'], unique=False)

    # ── users ────────────────────────────────────────────────────────────────
    # Add location-based matching fields
    op.add_column('users', sa.Column('latitude', sa.Float(), nullable=True))
    op.add_column('users', sa.Column('longitude', sa.Float(), nullable=True))
    op.add_column(
        'users',
        sa.Column(
            'preferred_match_radius_km',
            sa.Float(),
            nullable=True,
            server_default=sa.text('50'),
        ),
    )

    # ── pet_profiles ─────────────────────────────────────────────────────────
    # Add health certification fields
    op.add_column(
        'pet_profiles',
        sa.Column(
            'is_vaccinated',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    op.add_column(
        'pet_profiles',
        sa.Column('vaccination_date', sa.Date(), nullable=True),
    )
    op.add_column(
        'pet_profiles',
        sa.Column(
            'is_neutered',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    op.add_column(
        'pet_profiles',
        sa.Column(
            'is_trained',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )

    # ── matches ───────────────────────────────────────────────────────────────
    # Add soft-delete column + index
    op.add_column(
        'matches',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_matches_deleted_at', 'matches', ['deleted_at'], unique=False)

    # ── messages ──────────────────────────────────────────────────────────────
    # Add soft-delete timestamp (15-minute deletion window)
    op.add_column(
        'messages',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""

    # ── messages ──────────────────────────────────────────────────────────────
    op.drop_column('messages', 'deleted_at')

    # ── matches ───────────────────────────────────────────────────────────────
    op.drop_index('ix_matches_deleted_at', table_name='matches')
    op.drop_column('matches', 'deleted_at')

    # ── pet_profiles ─────────────────────────────────────────────────────────
    op.drop_column('pet_profiles', 'is_trained')
    op.drop_column('pet_profiles', 'is_neutered')
    op.drop_column('pet_profiles', 'vaccination_date')
    op.drop_column('pet_profiles', 'is_vaccinated')

    # ── users ────────────────────────────────────────────────────────────────
    op.drop_column('users', 'preferred_match_radius_km')
    op.drop_column('users', 'longitude')
    op.drop_column('users', 'latitude')

    # ── swipes ──────────────────────────────────────────────────────────────
    op.drop_index('ix_swipes_created_at', table_name='swipes')
    op.drop_column('swipes', 'undone_at')
    op.drop_column('swipes', 'is_undone')
