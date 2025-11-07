import os

class Config:
    # ✅ Custom secret key for secure session & password handling
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'MK65technologies'

    # ✅ SQLite database path (auto-created inside instance/)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///attendance.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
