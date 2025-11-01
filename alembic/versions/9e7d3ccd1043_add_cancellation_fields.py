"""add cancellation fields

Revision ID: 9e7d3ccd1043
Revises: f6203542bbfc
Create Date: 2025-11-01 14:17:48.585540

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e7d3ccd1043'
down_revision: Union[str, Sequence[str], None] = 'f6203542bbfc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None



def upgrade():
    op.add_column("layovers", sa.Column("cancelled_at", sa.DateTime(), nullable=True))
    op.add_column("layovers", sa.Column("cancellation_reason", sa.Text(), nullable=True))
    op.add_column("layovers", sa.Column("cancellation_notice_hours", sa.Integer(), nullable=True))

    op.add_column("layovers", sa.Column("cancellation_charge_applies", sa.Boolean(), nullable=False, server_default="0"))
    op.add_column("layovers", sa.Column("cancellation_charge_policy", sa.String(50), nullable=True))
    op.add_column("layovers", sa.Column("cancellation_charge_percent", sa.Integer(), nullable=True))
    op.add_column("layovers", sa.Column("cancellation_fee_cents", sa.Integer(), nullable=True))

def downgrade():
    op.drop_column("layovers", "cancellation_fee_cents")
    op.drop_column("layovers", "cancellation_charge_percent")
    op.drop_column("layovers", "cancellation_charge_policy")
    op.drop_column("layovers", "cancellation_charge_applies")
    op.drop_column("layovers", "cancellation_notice_hours")
    op.drop_column("layovers", "cancellation_reason")
    op.drop_column("layovers", "cancelled_at")