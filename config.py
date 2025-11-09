import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'MK65technologies'

    # Use PostgreSQL if DATABASE_URL exists; otherwise use SQLite locally
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///attendance.db'
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
