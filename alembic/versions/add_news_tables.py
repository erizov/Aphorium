"""Add news_articles, news_aphorisms, aphorism_news_pairs, news_notifications

Revision ID: add_news_tables
Revises: add_bilingual_group
Create Date: 2026-04-19

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "add_news_tables"
down_revision = "add_bilingual_group"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if inspect(conn).has_table("news_articles"):
        # Already present (e.g. created via init_db / SQLAlchemy create_all).
        return

    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("published_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("processed_at", sa.TIMESTAMP(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_articles_url", "news_articles", ["url"], unique=True)
    op.create_index(
        "idx_news_articles_published_at",
        "news_articles",
        ["published_at"],
        unique=False,
    )
    op.create_index(
        "idx_news_articles_category",
        "news_articles",
        ["category"],
        unique=False,
    )

    op.create_table(
        "news_aphorisms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("news_article_id", sa.Integer(), nullable=False),
        sa.Column("aphorism_text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False),
        sa.Column("generation_method", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(
            ["news_article_id"],
            ["news_articles.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_news_aphorisms_news_article_id",
        "news_aphorisms",
        ["news_article_id"],
        unique=False,
    )

    op.create_table(
        "aphorism_news_pairs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("quote_id", sa.Integer(), nullable=False),
        sa.Column("news_article_id", sa.Integer(), nullable=False),
        sa.Column("relevance_score", sa.Integer(), nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(), nullable=True),
        sa.ForeignKeyConstraint(
            ["news_article_id"],
            ["news_articles.id"],
        ),
        sa.ForeignKeyConstraint(
            ["quote_id"],
            ["quotes.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("quote_id", "news_article_id"),
    )
    op.create_index(
        "idx_aphorism_news_pairs_article",
        "aphorism_news_pairs",
        ["news_article_id"],
        unique=False,
    )

    op.create_table(
        "news_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("news_aphorism_id", sa.Integer(), nullable=False),
        sa.Column("delivery_method", sa.String(length=50), nullable=False),
        sa.Column("delivered_at", sa.TIMESTAMP(), nullable=True),
        sa.Column("recipient_id", sa.String(length=128), nullable=True),
        sa.ForeignKeyConstraint(
            ["news_aphorism_id"],
            ["news_aphorisms.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_news_notifications_news_aphorism_id",
        "news_notifications",
        ["news_aphorism_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop news tables if present (FK-safe order)."""
    conn = op.get_bind()
    for table in (
        "news_notifications",
        "aphorism_news_pairs",
        "news_aphorisms",
        "news_articles",
    ):
        if inspect(conn).has_table(table):
            op.drop_table(table)
