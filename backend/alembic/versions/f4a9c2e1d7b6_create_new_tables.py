"""create_new_tables

Revision ID: f4a9c2e1d7b6
Revises: e3f2a1b8c9d5
Create Date: 2026-06-14 01:00:00.000000

Creates the following new tables:
- favorites: pet-to-pet bookmark relationships with soft-delete
- blocks: user-to-user blocking for safety controls
- reports: user safety reports against other users/pets
- match_preferences: per-user match filter preferences
- message_reactions: emoji reactions on chat messages
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f4a9c2e1d7b6'
down_revision: Union[str, Sequence[str], None] = 'e3f2a1b8c9d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all new tables."""

    # ── favorites ────────────────────────────────────────────────────────────
    # Pet-to-pet bookmark relationships (one pet bookmarks another for later)
    op.create_table(
        'favorites',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'pet_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('pet_profiles.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'target_pet_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('pet_profiles.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'deleted_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.UniqueConstraint('pet_id', 'target_pet_id', name='uq_favorite_pair'),
        sa.CheckConstraint('pet_id != target_pet_id', name='ck_no_self_favorite'),
    )
    op.create_index('ix_favorites_pet_id', 'favorites', ['pet_id'], unique=False)
    op.create_index('ix_favorites_deleted_at', 'favorites', ['deleted_at'], unique=False)

    # ── blocks ───────────────────────────────────────────────────────────────
    # User-to-user blocking relationships for safety controls
    op.create_table(
        'blocks',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'blocking_user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'blocked_user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.UniqueConstraint('blocking_user_id', 'blocked_user_id', name='uq_block_pair'),
        sa.CheckConstraint('blocking_user_id != blocked_user_id', name='ck_no_self_block'),
    )
    op.create_index('ix_blocks_blocking_user', 'blocks', ['blocking_user_id'], unique=False)
    op.create_index('ix_blocks_blocked_user', 'blocks', ['blocked_user_id'], unique=False)

    # ── reports ──────────────────────────────────────────────────────────────
    # Safety reports filed by users against other users or pet profiles
    op.create_table(
        'reports',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'reporter_user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'reported_user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'reported_pet_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('pet_profiles.id', ondelete='CASCADE'),
            nullable=True,
        ),
        sa.Column('reason', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'resolved_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index('ix_reports_reporter', 'reports', ['reporter_user_id'], unique=False)
    op.create_index('ix_reports_reported', 'reports', ['reported_user_id'], unique=False)
    op.create_index('ix_reports_resolved', 'reports', ['resolved_at'], unique=False)

    # ── match_preferences ────────────────────────────────────────────────────
    # Per-user match filter preferences (one record per user)
    op.create_table(
        'match_preferences',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('preferred_species', sa.String(20), nullable=True),
        sa.Column('preferred_age_min', sa.Integer(), nullable=True),
        sa.Column('preferred_age_max', sa.Integer(), nullable=True),
        sa.Column('preferred_gender', sa.String(20), nullable=True),
        sa.Column(
            'preferred_radius_km',
            sa.Float(),
            nullable=True,
            server_default=sa.text('50'),
        ),
        sa.Column('breed_preferences', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.UniqueConstraint('user_id', name='uq_one_preference_per_user'),
        sa.CheckConstraint(
            'preferred_age_min IS NULL OR preferred_age_max IS NULL OR preferred_age_min <= preferred_age_max',
            name='ck_age_range_valid',
        ),
        sa.CheckConstraint(
            'preferred_radius_km IS NULL OR (preferred_radius_km >= 1 AND preferred_radius_km <= 500)',
            name='ck_radius_valid',
        ),
    )
    op.create_index('ix_match_preferences_user_id', 'match_preferences', ['user_id'], unique=False)

    # ── message_reactions ─────────────────────────────────────────────────────
    # Emoji reactions attached to individual chat messages
    op.create_table(
        'message_reactions',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'message_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('messages.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('emoji', sa.String(32), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.UniqueConstraint('message_id', 'user_id', name='uq_message_reaction_user'),
    )
    op.create_index('ix_message_reactions_message_id', 'message_reactions', ['message_id'], unique=False)
    op.create_index('ix_message_reactions_user_id', 'message_reactions', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop all new tables in reverse creation order."""

    # ── message_reactions ─────────────────────────────────────────────────────
    op.drop_index('ix_message_reactions_user_id', table_name='message_reactions')
    op.drop_index('ix_message_reactions_message_id', table_name='message_reactions')
    op.drop_table('message_reactions')

    # ── match_preferences ────────────────────────────────────────────────────
    op.drop_index('ix_match_preferences_user_id', table_name='match_preferences')
    op.drop_table('match_preferences')

    # ── reports ──────────────────────────────────────────────────────────────
    op.drop_index('ix_reports_resolved', table_name='reports')
    op.drop_index('ix_reports_reported', table_name='reports')
    op.drop_index('ix_reports_reporter', table_name='reports')
    op.drop_table('reports')

    # ── blocks ───────────────────────────────────────────────────────────────
    op.drop_index('ix_blocks_blocked_user', table_name='blocks')
    op.drop_index('ix_blocks_blocking_user', table_name='blocks')
    op.drop_table('blocks')

    # ── favorites ────────────────────────────────────────────────────────────
    op.drop_index('ix_favorites_deleted_at', table_name='favorites')
    op.drop_index('ix_favorites_pet_id', table_name='favorites')
    op.drop_table('favorites')
