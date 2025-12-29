"""Add bilingual_group_id to quotes table

Revision ID: add_bilingual_group
Revises: 
Create Date: 2025-12-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_bilingual_group'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add bilingual_group_id column to quotes table."""
    # Add column
    op.add_column(
        'quotes',
        sa.Column('bilingual_group_id', sa.Integer(), nullable=True)
    )
    
    # Create index for fast lookups
    op.create_index(
        'idx_quotes_bilingual_group',
        'quotes',
        ['bilingual_group_id']
    )
    
    # Create index for language + group (for bilingual pair queries)
    op.create_index(
        'idx_quotes_group_language',
        'quotes',
        ['bilingual_group_id', 'language']
    )


def downgrade():
    """Remove bilingual_group_id column."""
    op.drop_index('idx_quotes_group_language', table_name='quotes')
    op.drop_index('idx_quotes_bilingual_group', table_name='quotes')
    op.drop_column('quotes', 'bilingual_group_id')

