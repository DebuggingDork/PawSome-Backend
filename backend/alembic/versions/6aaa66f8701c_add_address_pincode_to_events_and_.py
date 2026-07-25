"""add_address_pincode_to_events_and_playdates

Revision ID: 6aaa66f8701c
Revises: 89165e008650
Create Date: 2026-07-25 18:32:10.898475

Adds:
- events.address / events.pincode
- playdates.address / playdates.pincode

Both already had location_name/latitude/longitude; this brings them in line
with users and pet_profiles so every location-capturing surface in the app
stores the same four fields (lat/lng for distance, address for display,
pincode for filtering/future features).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6aaa66f8701c'
down_revision: Union[str, Sequence[str], None] = '89165e008650'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('events', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('events', sa.Column('pincode', sa.String(length=20), nullable=True))
    op.add_column('playdates', sa.Column('address', sa.Text(), nullable=True))
    op.add_column('playdates', sa.Column('pincode', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('playdates', 'pincode')
    op.drop_column('playdates', 'address')
    op.drop_column('events', 'pincode')
    op.drop_column('events', 'address')
