from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'df255194ce77'
down_revision = '7ae04c9bb0b2'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE broadcast_seen_new (
            id INTEGER PRIMARY KEY,
            broadcast_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_broadcast_user_seen UNIQUE (broadcast_id, user_id),
            FOREIGN KEY(broadcast_id) REFERENCES broadcasts (id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users (id)
        );
    """))

    conn.execute(sa.text("""
        INSERT INTO broadcast_seen_new (id, broadcast_id, user_id, seen_at)
        SELECT id, broadcast_id, user_id, seen_at FROM broadcast_seen;
    """))

    conn.execute(sa.text("DROP TABLE broadcast_seen;"))
    conn.execute(sa.text("ALTER TABLE broadcast_seen_new RENAME TO broadcast_seen;"))


def downgrade():
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE broadcast_seen_old (
            id INTEGER PRIMARY KEY,
            broadcast_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT uq_broadcast_user_seen UNIQUE (broadcast_id, user_id),
            FOREIGN KEY(broadcast_id) REFERENCES broadcasts (id),
            FOREIGN KEY(user_id) REFERENCES users (id)
        );
    """))

    conn.execute(sa.text("""
        INSERT INTO broadcast_seen_old (id, broadcast_id, user_id, seen_at)
        SELECT id, broadcast_id, user_id, seen_at FROM broadcast_seen;
    """))

    conn.execute(sa.text("DROP TABLE broadcast_seen;"))
    conn.execute(sa.text("ALTER TABLE broadcast_seen_old RENAME TO broadcast_seen;"))
