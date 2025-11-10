from app import create_app, db

app = create_app()

if __name__ == "__main__":
    # Test DB connection or use for Flask-Migrate commands
    with app.app_context():
        print("DB URL:", app.config['SQLALCHEMY_DATABASE_URI'])
