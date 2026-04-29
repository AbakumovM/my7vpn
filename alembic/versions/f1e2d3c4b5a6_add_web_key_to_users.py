"""add web_key to users

Revision ID: f1e2d3c4b5a6
Revises: a3f8d2c1e9b0
Create Date: 2026-04-26 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f1e2d3c4b5a6"
down_revision: Union[str, None] = "a3f8d2c1e9b0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("web_key", sa.String(36), nullable=True))
    op.create_index("ix_users_web_key", "users", ["web_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_web_key", table_name="users")
    op.drop_column("users", "web_key")
