from flask_socketio import emit, join_room, leave_room
from flask_login import current_user
from app import socketio

@socketio.on('connect')
def handle_connect():
    # When a client connects, if logged-in, join user and company rooms
    try:
        if current_user and getattr(current_user, "is_authenticated", False):
            uid = current_user.id
            join_room(f"user_{uid}")
            if getattr(current_user, "company_id", None):
                join_room(f"company_{current_user.company_id}")
            # Optionally: emit an acknowledgement
            emit('connected', {"msg": "connected", "user_id": uid})
    except Exception:
        # unauthenticated clients will not join rooms
        pass

@socketio.on('disconnect')
def handle_disconnect():
    try:
        if current_user and getattr(current_user, "is_authenticated", False):
            if getattr(current_user, "company_id", None):
                leave_room(f"company_{current_user.company_id}")
    except Exception:
        pass
