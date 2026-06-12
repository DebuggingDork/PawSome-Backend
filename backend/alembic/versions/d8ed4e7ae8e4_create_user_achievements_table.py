"""create_user_achievements_table

Revision ID: d8ed4e7ae8e4
Revises: a47376de7603
Create Date: 2026-06-13 01:46:26.178944

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8ed4e7ae8e4'
down_revision: Union[str, Sequence[str], None] = 'a47376de7603'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'user_achievements',
        sa.Column('id', sa.UUID(), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('achievement_type', sa.String(length=50), nullable=False),
        sa.Column('earned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'achievement_type', name='uq_user_achievement')
    )
    op.create_index('ix_user_achievements_user_id', 'user_achievements', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_user_achievements_user_id', 'user_achievements')
    op.drop_table('user_achievements')
