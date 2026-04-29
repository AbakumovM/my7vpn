"""add user_subscriptions and user_payments

Revision ID: a3f8d2c1e9b0
Revises: 852024dfadfe
Create Date: 2026-04-25 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f8d2c1e9b0"
down_revision: Union[str, None] = "852024dfadfe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "user_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_limit", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.create_table(
        "user_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_telegram_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column(
            "subscription_id",
            sa.Integer(),
            sa.ForeignKey("user_subscriptions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("device_limit", sa.Integer(), server_default="1", nullable=False),
        sa.Column("payment_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(), nullable=True),
        sa.Column("payment_method", sa.String(), nullable=True),
        sa.Column("status", sa.String(20), server_default="success", nullable=False),
        sa.Column("external_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("user_payments")
    op.drop_table("user_subscriptions")
