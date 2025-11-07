from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.forms import LoginForm
from app.models import User
from app import db, login_manager

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


# --------------------------------------
# Ensure Default Admin User Exists
# --------------------------------------
def ensure_default_admin():
    """Create a default admin account if it doesn't exist."""
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            first_name="System",
            last_name="Admin",
            username="admin",
            email="admin@officeconnect.local",
            role="admin",
            is_active=True
        )
        admin.set_password("admin123")  # Default password
        db.session.add(admin)
        db.session.commit()
        print("✅ Default admin user created: username='admin', password='admin123'")


# --------------------------------------
# Login Route (Database-based)
# --------------------------------------
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    # Ensure default admin exists before login
    ensure_default_admin()

    # Redirect if already logged in
    if current_user.is_authenticated:
        if current_user.role == "admin":
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == "supervisor":
            return redirect(url_for('supervisor.dashboard'))
        elif current_user.role == "agent":
            return redirect(url_for('agent.dashboard'))
        return redirect(url_for('auth.login'))

    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        password = form.password.data

        user = User.query.filter_by(username=username).first()

        # Invalid credentials
        if not user or not user.check_password(password):
            flash("❌ Invalid username or password", "danger")
            return redirect(url_for('auth.login'))  # 🔹 Important: stop further code

        # Inactive user
        if not user.is_active:
            flash("⚠️ Your account is deactivated. Please contact admin.", "warning")
            return redirect(url_for('auth.login'))

        # Successful login
        login_user(user)
        flash(f"✅ Welcome, {user.first_name or user.username}!", "success")

        # Redirect by role
        if user.role == "admin":
            return redirect(url_for('admin.dashboard'))
        elif user.role == "supervisor":
            return redirect(url_for('supervisor.dashboard'))
        elif user.role == "agent":
            return redirect(url_for('agent.dashboard'))
        else:
            flash("⚠️ Unknown role type.", "warning")
            return redirect(url_for('auth.login'))

    # If GET request or form invalid
    return render_template('login.html', form=form)


# --------------------------------------
# Logout Route
# --------------------------------------
@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("👋 Logged out successfully.", "info")
    return redirect(url_for('auth.login'))


# --------------------------------------
# Flask-Login User Loader
# --------------------------------------
@login_manager.user_loader
def load_user(user_id):
    """Reload user from session using database."""
    return User.query.get(int(user_id))
