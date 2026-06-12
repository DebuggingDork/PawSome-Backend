"""create_swipes_matches_notifications_tables

Revision ID: 08edcca036c1
Revises: b5e938cdcb09
Create Date: 2026-06-13 00:41:40.590905

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08edcca036c1'
down_revision: Union[str, Sequence[str], None] = 'b5e938cdcb09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create swipe_action enum
    op.execute("CREATE TYPE swipe_action AS ENUM ('like', 'skip')")
    
    # Create notification_type enum
    op.execute("CREATE TYPE notification_type AS ENUM ('new_match', 'new_like')")
    
    # Create swipes table
    op.create_table(
        'swipes',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('swiper_pet_id', sa.UUID(), nullable=False),
        sa.Column('target_pet_id', sa.UUID(), nullable=False),
        sa.Column('action', sa.Enum('like', 'skip', name='swipe_action', native_enum=False, length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['swiper_pet_id'], ['pet_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_pet_id'], ['pet_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('swiper_pet_id', 'target_pet_id', name='uq_swipe_pair')
    )
    op.create_index(op.f('ix_swipes_swiper_pet_id'), 'swipes', ['swiper_pet_id'], unique=False)
    op.create_index(op.f('ix_swipes_target_pet_id'), 'swipes', ['target_pet_id'], unique=False)
    op.create_index('ix_swipes_target_action', 'swipes', ['target_pet_id', 'action'], unique=False)
    
    # Create matches table
    op.create_table(
        'matches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('pet1_id', sa.UUID(), nullable=False),
        sa.Column('pet2_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['pet1_id'], ['pet_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pet2_id'], ['pet_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pet1_id', 'pet2_id', name='uq_match_pair')
    )
    op.create_index('ix_matches_pet1', 'matches', ['pet1_id'], unique=False)
    op.create_index('ix_matches_pet2', 'matches', ['pet2_id'], unique=False)
    
    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('notification_type', sa.Enum('new_match', 'new_like', name='notification_type', native_enum=False, length=20), nullable=False),
        sa.Column('pet_id', sa.UUID(), nullable=False),
        sa.Column('related_pet_id', sa.UUID(), nullable=False),
        sa.Column('match_id', sa.UUID(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['related_pet_id'], ['pet_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
    
    op.drop_index('ix_matches_pet2', table_name='matches')
    op.drop_index('ix_matches_pet1', table_name='matches')
    op.drop_table('matches')
    
    op.drop_index('ix_swipes_target_action', table_name='swipes')
    op.drop_index(op.f('ix_swipes_target_pet_id'), table_name='swipes')
    op.drop_index(op.f('ix_swipes_swiper_pet_id'), table_name='swipes')
    op.drop_table('swipes')
    
    op.execute('DROP TYPE notification_type')
    op.execute('DROP TYPE swipe_action')
