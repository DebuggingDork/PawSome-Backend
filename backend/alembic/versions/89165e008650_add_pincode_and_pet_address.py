"""add_pincode_and_pet_address

Revision ID: 89165e008650
Revises: bcb4de2a550a
Create Date: 2026-07-25 15:13:12.878734

Adds:
- users.pincode: postal code captured alongside the existing address/lat/lng,
  either from reverse-geocoding "use current location" or picking an address
  suggestion.
- pet_profiles.address / pet_profiles.pincode: pets only had lat/lng before,
  no human-readable address — bringing them in line with users so a pet's
  location can show/edit the same way.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '89165e008650'
down_revision: Union[str, Sequence[str], None] = 'bcb4de2a550a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('pincode', sa.String(length=20), nullable=True))
    op.add_column('pet_profiles', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('pet_profiles', sa.Column('pincode', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('pet_profiles', 'pincode')
    op.drop_column('pet_profiles', 'address')
    op.drop_column('users', 'pincode')
