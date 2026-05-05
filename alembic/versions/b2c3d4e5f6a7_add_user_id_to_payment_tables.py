"""add user_id to user_payments and pending_payments

Revision ID: b2c3d4e5f6a7
Revises: f1e2d3c4b5a6
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'f1e2d3c4b5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user_payments: add user_id FK, make user_telegram_id nullable, backfill
    op.add_column(
        'user_payments',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    )
    op.execute(
        "UPDATE user_payments up SET user_id = u.id FROM users u WHERE u.telegram_id = up.user_telegram_id"
    )
    op.alter_column('user_payments', 'user_telegram_id', nullable=True)
    op.create_index('ix_user_payments_user_id', 'user_payments', ['user_id'])

    # pending_payments: add user_id FK, make user_telegram_id nullable, backfill
    op.add_column(
        'pending_payments',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True)
    )
    op.execute(
        "UPDATE pending_payments pp SET user_id = u.id FROM users u WHERE u.telegram_id = pp.user_telegram_id"
    )
    op.alter_column('pending_payments', 'user_telegram_id', nullable=True)
    op.create_index('ix_pending_payments_user_id', 'pending_payments', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_user_payments_user_id', table_name='user_payments')
    op.drop_column('user_payments', 'user_id')
    op.alter_column('user_payments', 'user_telegram_id', nullable=False)
    op.drop_index('ix_pending_payments_user_id', table_name='pending_payments')
    op.drop_column('pending_payments', 'user_id')
    op.alter_column('pending_payments', 'user_telegram_id', nullable=False)
