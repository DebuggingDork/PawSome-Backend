"""create_chat_participants_table

Revision ID: 1379710dc834
Revises: abcb794c8f9d
Create Date: 2026-06-13 01:05:08.915386

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1379710dc834'
down_revision: Union[str, Sequence[str], None] = 'abcb794c8f9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'chat_participants',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('match_id', sa.UUID(), nullable=False),
        sa.Column('pet_id', sa.UUID(), nullable=False),
        sa.Column('last_read_message_id', sa.UUID(), nullable=True),
        sa.Column('last_read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pet_id'], ['pet_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['last_read_message_id'], ['messages.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('match_id', 'pet_id', name='uq_chat_participant')
    )
    op.create_index(op.f('ix_chat_participants_match_id'), 'chat_participants', ['match_id'], unique=False)
    op.create_index(op.f('ix_chat_participants_pet_id'), 'chat_participants', ['pet_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_chat_participants_pet_id'), table_name='chat_participants')
    op.drop_index(op.f('ix_chat_participants_match_id'), table_name='chat_participants')
    op.drop_table('chat_participants')
