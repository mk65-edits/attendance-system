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

# ✅ Run app using SocketIO with Eventlet
if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    # 🔹 host="0.0.0.0" allows access from other devices on your local network
    # 🔹 debug=True is fine for local development (not production)
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
