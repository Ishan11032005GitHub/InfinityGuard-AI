"""Account-level one-time payment limits.

Revision ID: 20260702_0007
Revises: 20260701_0006
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260702_0007"
down_revision = "20260701_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "account_preferences" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("account_preferences")}
    if "one_time_payment_limit" not in columns:
        op.add_column(
            "account_preferences",
            sa.Column("one_time_payment_limit", sa.Float(), nullable=False, server_default="5000"),
        )
        op.alter_column("account_preferences", "one_time_payment_limit", server_default=None)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "account_preferences" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("account_preferences")}
    if "one_time_payment_limit" in columns:
        op.drop_column("account_preferences", "one_time_payment_limit")
