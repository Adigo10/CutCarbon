"""offset credit integrity metadata on offset_purchases

Adds the evidence a post-2026 compensation claim needs against a retired credit:
an integrity label (ICVCM CCP approval or a Paris Article 6.4 corresponding
adjustment) plus a traceable registry retirement (serial + date), alongside the
crediting methodology and host country. See app/services/offset_integrity.py.

All columns are nullable — purchases recorded before the registry paperwork lands
stay valid, they just are not claim-eligible until the evidence is complete.

`offset_purchases` is already RLS-enabled with anon/authenticated grants revoked
(a1b2c3d4e5f6 / b2c3d4e5f6a7); adding columns to a locked table creates no new
grantable object, so no lockdown step is repeated here.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "offset_purchases"

# (name, type) — built fresh per call so a Column object is never reused across ops.
_COLUMNS = [
    ("ccp_approved", sa.Boolean()),
    ("article6_adjustment", sa.Boolean()),
    ("methodology", sa.String()),
    ("retirement_serial", sa.String()),
    ("retirement_date", sa.Date()),
    ("country", sa.String()),
]


def upgrade() -> None:
    for name, type_ in _COLUMNS:
        op.add_column(_TABLE, sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _type in reversed(_COLUMNS):
        op.drop_column(_TABLE, name)
