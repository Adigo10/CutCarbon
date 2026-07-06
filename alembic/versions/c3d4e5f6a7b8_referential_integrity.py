"""referential integrity: user_id NOT NULL, ON DELETE CASCADE, users->auth.users FK

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column, referred_table, referred_column) for the intra-public FKs.
_CHILD_FKS = [
    ("scenarios", "user_id", "users", "id"),
    ("chat_messages", "user_id", "users", "id"),
    ("financial_reports", "user_id", "users", "id"),
    ("financial_reports", "scenario_id", "scenarios", "id"),
    ("offset_purchases", "user_id", "users", "id"),
    ("offset_purchases", "scenario_id", "scenarios", "id"),
]
_NOT_NULL = [("scenarios", "user_id"), ("chat_messages", "user_id"), ("financial_reports", "user_id")]


def _drop_existing_fk(table: str, column: str) -> None:
    """Drop whatever FK currently constrains (table, column), by discovered name."""
    op.execute(
        f"""
        DO $$
        DECLARE cname text;
        BEGIN
            SELECT con.conname INTO cname
              FROM pg_constraint con
              JOIN pg_attribute att
                ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
             WHERE con.conrelid = 'public.{table}'::regclass
               AND con.contype = 'f'
               AND att.attname = '{column}'
             LIMIT 1;
            IF cname IS NOT NULL THEN
                EXECUTE format('ALTER TABLE public.{table} DROP CONSTRAINT %I', cname);
            END IF;
        END $$;
        """
    )


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    for table, column in _NOT_NULL:
        op.alter_column(table, column, existing_type=sa.Uuid(as_uuid=False), nullable=False)

    for table, column, ref_table, ref_col in _CHILD_FKS:
        _drop_existing_fk(table, column)
        op.execute(
            f'ALTER TABLE public.{table} ADD CONSTRAINT {table}_{column}_fkey '
            f"FOREIGN KEY ({column}) REFERENCES public.{ref_table}({ref_col}) ON DELETE CASCADE"
        )

    # Tie the app profile to Supabase's auth.users so auth deletions cascade (GDPR erasure).
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'users_id_auth_users_fkey'
            ) THEN
                ALTER TABLE public.users
                    ADD CONSTRAINT users_id_auth_users_fkey
                    FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return

    op.execute("ALTER TABLE public.users DROP CONSTRAINT IF EXISTS users_id_auth_users_fkey")

    for table, column, ref_table, ref_col in _CHILD_FKS:
        _drop_existing_fk(table, column)
        op.execute(
            f'ALTER TABLE public.{table} ADD CONSTRAINT {table}_{column}_fkey '
            f"FOREIGN KEY ({column}) REFERENCES public.{ref_table}({ref_col})"
        )

    for table, column in _NOT_NULL:
        op.alter_column(table, column, existing_type=sa.Uuid(as_uuid=False), nullable=True)
