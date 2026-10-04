"""Persistent factor catalog and chat citations.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from app.models.db_security import lock_down_tables

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(JSONB, "postgresql")
    op.add_column("chat_messages", sa.Column("citations", json_type, nullable=True))
    op.create_table(
        "factor_catalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document", json_type, nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("refresh_token", sa.String(), nullable=True),
        sa.Column("refresh_expires_at", sa.DateTime(), nullable=True),
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        lock_down_tables(bind, ["factor_catalog"])
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON public.factor_catalog TO cutcarbon_app")
        op.execute("CREATE POLICY app_all ON public.factor_catalog FOR ALL TO cutcarbon_app USING (true) WITH CHECK (true)")
    # Startup seeds the singleton from the packaged catalog, including SQLite dev.


def downgrade():
    op.drop_table("factor_catalog")
    op.drop_column("chat_messages", "citations")
