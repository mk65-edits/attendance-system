"""Fix penalty and clearance relationships (SQLite-safe, clean create)

Revision ID: 577d6aa1171c
Revises: 98426c47421a
Create Date: 2025-11-04 02:56:06.626508
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '577d6aa1171c'
down_revision = '98426c47421a'
branch_labels = None
depends_on = None


def upgrade():
    # Drop old temporary or partial tables if they exist
    op.execute("DROP TABLE IF EXISTS _clearances_old;")
    op.execute("DROP TABLE IF EXISTS _penalties_old;")
    op.execute("DROP TABLE IF EXISTS clearances;")
    op.execute("DROP TABLE IF EXISTS penalties;")

    # ------------------ Clearances ------------------
    op.execute("""
        CREATE TABLE clearances (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount FLOAT NOT NULL,
            reason VARCHAR(255),
            date_added DATETIME DEFAULT CURRENT_TIMESTAMP,
            marked_by INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            CONSTRAINT fk_clearances_marked_by_users FOREIGN KEY(marked_by) REFERENCES users(id)
        );
    """)

    # ------------------ Penalties ------------------
    op.execute("""
        CREATE TABLE penalties (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            amount FLOAT NOT NULL,
            reason VARCHAR(255),
            date_added DATETIME DEFAULT CURRENT_TIMESTAMP,
            marked_by INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            CONSTRAINT fk_penalties_marked_by_users FOREIGN KEY(marked_by) REFERENCES users(id)
        );
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS penalties;")
    op.execute("DROP TABLE IF EXISTS clearances;")
