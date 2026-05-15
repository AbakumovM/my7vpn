"""add status to pending_payments

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-05
"""
import sqlalchemy as sa

from alembic import op

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'pending_payments',
        sa.Column(
            'status',
            sa.String(20),
            nullable=False,
            server_default='pending',
        )
    )


def downgrade() -> None:
    op.drop_column('pending_payments', 'status')
