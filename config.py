import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'MK65technologies'

    DATABASE_URL = os.environ.get('DATABASE_URL')

    # Detect DATABASE_URL and prepend psycopg2 driver if missing
    if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
        SQLALCHEMY_DATABASE_URI = DATABASE_URL.replace(
            "postgresql://",
            "postgresql+psycopg2://"
        )
    else:
        # Fallback to SQLite locally
        SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///attendance.db'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
