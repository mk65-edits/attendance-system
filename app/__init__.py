from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_socketio import SocketIO
from config import Config

# ---------------------------------------
# Initialize Flask Extensions
# ---------------------------------------
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
socketio = SocketIO(cors_allowed_origins="*")  # For real-time updates (broadcasts, etc.)

# Flask-Login setup
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'


def create_app():
    """Application factory setup."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # ---------------------------------------
    # Initialize Extensions with App
    # ---------------------------------------
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")

    # ---------------------------------------
    # Import Models
    # ---------------------------------------
    from app.models import User

    # ---------------------------------------
    # Register Blueprints (Routes)
    # ---------------------------------------
    from app.routes.auth_routes import auth_bp
    from app.routes.admin_routes import admin_bp
    from app.routes.agent_routes import agent_bp
    from app.routes.supervisor_routes import supervisor_bp
    from app.routes.broadcasts import bp as broadcasts_bp

    # Register all blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(supervisor_bp)
    app.register_blueprint(broadcasts_bp)

    # ---------------------------------------
    # Inject Global Variables into Templates
    # ---------------------------------------
    @app.context_processor
    def inject_globals():
        return dict(app_name="Office Connect")

    # ---------------------------------------
    # Ensure Default Admin Exists
    # ---------------------------------------
    def ensure_default_admin():
        from werkzeug.security import generate_password_hash
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                first_name="System",
                last_name="Admin",
                username="admin",
                email="admin@officeconnect.local",
                role="admin",
                is_active=True,
                password_hash=generate_password_hash("admin123")
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Default admin created (username='admin', password='admin123')")

    # ---------------------------------------
    # Ensure Database Tables Exist & Create Admin
    # ---------------------------------------
    with app.app_context():
        db.create_all()           # Create tables if they don’t exist
        ensure_default_admin()    # Safe, runs once at startup

    return app
