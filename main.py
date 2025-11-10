import eventlet
eventlet.monkey_patch()  # ✅ must be first

from flask import redirect, url_for
from app import create_app, socketio  # do NOT import db here

# Create Flask app
app = create_app()

# Root redirect to login page
@app.route('/')
def home_redirect():
    return redirect(url_for('auth.login'))

if __name__ == "__main__":
    # Run with Eventlet for WebSockets support
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000,
        debug=True,           # Set to False in production
        use_reloader=True,    # Optional: auto-reload on code changes
    )
