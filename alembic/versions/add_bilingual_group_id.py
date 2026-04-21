"""Add bilingual_group_id to quotes table

Revision ID: add_bilingual_group
Revises: 
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_bilingual_group'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add bilingual_group_id column to quotes table."""
    conn = op.get_bind()
    insp = inspect(conn)
    cols = {c["name"] for c in insp.get_columns("quotes")}
    if "bilingual_group_id" not in cols:
        op.add_column(
            "quotes",
            sa.Column("bilingual_group_id", sa.Integer(), nullable=True),
        )
    insp = inspect(conn)
    ix_names = {i["name"] for i in insp.get_indexes("quotes")}
    if "idx_quotes_bilingual_group" not in ix_names:
        op.create_index(
            "idx_quotes_bilingual_group",
            "quotes",
            ["bilingual_group_id"],
        )
    if "idx_quotes_group_language" not in ix_names:
        op.create_index(
            "idx_quotes_group_language",
            "quotes",
            ["bilingual_group_id", "language"],
        )


def downgrade():
    """Remove bilingual_group_id column."""
    conn = op.get_bind()
    insp = inspect(conn)
    ix_names = {i["name"] for i in insp.get_indexes("quotes")}
    if "idx_quotes_group_language" in ix_names:
        op.drop_index("idx_quotes_group_language", table_name="quotes")
    if "idx_quotes_bilingual_group" in ix_names:
        op.drop_index("idx_quotes_bilingual_group", table_name="quotes")
    cols = {c["name"] for c in insp.get_columns("quotes")}
    if "bilingual_group_id" in cols:
        op.drop_column("quotes", "bilingual_group_id")

