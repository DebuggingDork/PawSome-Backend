"""create_messages_table

Revision ID: abcb794c8f9d
Revises: 08edcca036c1
Create Date: 2026-06-13 00:58:43.971307

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abcb794c8f9d'
down_revision: Union[str, Sequence[str], None] = '08edcca036c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'messages',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('match_id', sa.UUID(), nullable=False),
        sa.Column('sender_pet_id', sa.UUID(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('msg_type', sa.String(length=20), nullable=False, server_default='text'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.ForeignKeyConstraint(['match_id'], ['matches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sender_pet_id'], ['pet_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_match_id'), 'messages', ['match_id'], unique=False)
    op.create_index(op.f('ix_messages_sender_pet_id'), 'messages', ['sender_pet_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_messages_sender_pet_id'), table_name='messages')
    op.drop_index(op.f('ix_messages_match_id'), table_name='messages')
    op.drop_table('messages')
