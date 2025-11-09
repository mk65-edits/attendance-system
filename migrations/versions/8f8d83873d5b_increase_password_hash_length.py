"""Increase password_hash length

Revision ID: 8f8d83873d5b
Revises: 9f445df6e88e
Create Date: 2025-11-10 02:20:13.355006
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '8f8d83873d5b'
down_revision = '9f445df6e88e'
branch_labels = None
depends_on = None


def upgrade():
    # Use batch_alter_table for SQLite
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'password_hash',
            existing_type=sa.String(length=128),
            type_=sa.String(length=512),
            existing_nullable=False
        )


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column(
            'password_hash',
            existing_type=sa.String(length=512),
            type_=sa.String(length=128),
            existing_nullable=False
        )
