"""add_user_profile_fields

Revision ID: a47376de7603
Revises: 1379710dc834
Create Date: 2026-06-13 01:32:02.341837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a47376de7603'
down_revision: Union[str, Sequence[str], None] = '1379710dc834'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('full_name', sa.String(length=200), nullable=True))
    op.add_column('users', sa.Column('occupation', sa.String(length=200), nullable=True))
    op.add_column('users', sa.Column('bio', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('profile_photo_url', sa.String(length=512), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'profile_photo_url')
    op.drop_column('users', 'address')
    op.drop_column('users', 'bio')
    op.drop_column('users', 'occupation')
    op.drop_column('users', 'full_name')
