"""Add created_at column to penalties

Revision ID: 9f445df6e88e
Revises: 577d6aa1171c
Create Date: 2025-11-05 15:20:58.936077
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f445df6e88e'
down_revision = '577d6aa1171c'
branch_labels = None
depends_on = None


def upgrade():
    # ✅ Only modify the penalties table
    with op.batch_alter_table('penalties', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch_op.alter_column(
            'id',
            existing_type=sa.INTEGER(),
            nullable=False,
            autoincrement=True
        )
        batch_op.alter_column(
            'reason',
            existing_type=sa.VARCHAR(length=255),
            nullable=False
        )
        batch_op.drop_column('date_added')


def downgrade():
    with op.batch_alter_table('penalties', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'date_added',
                sa.DATETIME(),
                server_default=sa.text('(CURRENT_TIMESTAMP)'),
                nullable=True
            )
        )
        batch_op.alter_column(
            'reason',
            existing_type=sa.VARCHAR(length=255),
            nullable=True
        )
        batch_op.alter_column(
            'id',
            existing_type=sa.INTEGER(),
            nullable=True,
            autoincrement=True
        )
        batch_op.drop_column('created_at')
