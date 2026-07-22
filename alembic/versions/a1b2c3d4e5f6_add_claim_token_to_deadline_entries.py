"""add claim token to deadline entries

Revision ID: a1b2c3d4e5f6
Revises: 28e3ade3a69a
Create Date: 2026-07-22 12:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '28e3ade3a69a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add column claim_token to deadline_entries table with SQLite batch alters
    with op.batch_alter_table('deadline_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('claim_token', sa.String(length=255), nullable=True))
        batch_op.create_index(batch_op.f('ix_deadline_entries_claim_token'), ['claim_token'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('deadline_entries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_deadline_entries_claim_token'))
        batch_op.drop_column('claim_token')
