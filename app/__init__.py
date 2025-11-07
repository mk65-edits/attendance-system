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
    socketio.init_app(app)  # ✅ Initialize SocketIO here

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
    # CLI Command: Create Default Admin
    # ---------------------------------------
    @app.cli.command("create-admin")
    def create_admin():
        """Creates a default global admin user if none exists."""
        from werkzeug.security import generate_password_hash

        with app.app_context():
            admin = User.query.filter_by(username='admin').first()
            if not admin:
                admin = User(
                    first_name='System',
                    last_name='Admin',
                    username='admin',
                    email='admin@officeconnect.local',
                    role='admin',  # Global admin
                    company=None,  # No company assigned
                    password_hash=generate_password_hash('MK65technologies')
                )
                db.session.add(admin)
                db.session.commit()
                print("✅ Default admin created (username: admin, password: MK65technologies)")
            else:
                print("⚠️ Admin already exists.")


    # ---------------------------------------
    # Ensure Database Tables Exist
    # ---------------------------------------
    with app.app_context():
        db.create_all()

    return app
