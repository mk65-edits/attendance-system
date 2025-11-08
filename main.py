import eventlet
eventlet.monkey_patch()  # ✅ must be FIRST, before any other imports

from flask import redirect, url_for
from app import create_app, db, socketio

# ✅ Create Flask app
app = create_app()

# ✅ Root redirect to login page
@app.route('/')
def home_redirect():
    return redirect(url_for('auth.login'))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Ensure tables exist before starting

    # 🔹 Run with Eventlet for WebSockets support
    # 🔹 host="0.0.0.0" allows network access
    # 🔹 debug=True for local development only
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,           # Set to False in production
        use_reloader=True,    # Optional: auto-reload on code changes
    )
