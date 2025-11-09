from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app import db, socketio
from app.models import Broadcast, BroadcastSeen, User, Company
from datetime import datetime, timezone
from sqlalchemy import or_
from collections import defaultdict
from flask_socketio import emit
import pytz

bp = Blueprint("broadcasts", __name__, url_prefix="/broadcasts")

# ==========================================================
# 🔹 ADMIN: Create a new broadcast (form POST)
# ==========================================================
@bp.route("/create", methods=["POST"])
@login_required
def create_broadcast():
    if current_user.role != "admin":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("admin.dashboard"))

    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()
    target = request.form.get("target", "all").strip()
    company_id = request.form.get("company_id") or None

    if not message:
        flash("Message is required.", "danger")
        return redirect(request.referrer or url_for("broadcasts.view_broadcasts"))

    # 🔹 Set timezone (Pakistan Standard Time example)
    PKT = pytz.timezone("Asia/Karachi")
    now = datetime.now(PKT)

    # ✅ Create broadcast entry with timezone-aware datetime
    b = Broadcast(
        sender_id=current_user.id,
        title=title or None,
        message=message,
        target=target,
        company_id=company_id,
        created_at=now
    )
    db.session.add(b)
    db.session.commit()

    payload = b.to_dict()

    # ✅ Determine recipients
    if target == "all":
        recipients_query = User.query
    elif target == "company" and company_id:
        recipients_query = User.query.filter(User.company_id == int(company_id))
    elif target == "supervisors":
        recipients_query = User.query.filter(User.role == "supervisor")
    elif target == "supervisors_company" and company_id:
        recipients_query = User.query.filter(
            User.role == "supervisor",
            User.company_id == int(company_id)
        )
    else:
        recipients_query = User.query

    recipient_ids = [r.id for r in recipients_query.with_entities(User.id).all()]

    # ✅ Emit to each recipient via Socket.IO
    for uid in recipient_ids:
        socketio.emit("new_broadcast", payload, room=f"user_{uid}")

    socketio.emit("admin_broadcast_update", payload)
    flash("Broadcast sent successfully!", "success")

    return redirect(url_for("broadcasts.view_broadcasts"))

# ==========================================================
# 🔹 API: Fetch unread broadcasts
# ==========================================================
@bp.route("/unread", methods=["GET"])
@login_required
def unread_broadcasts():
    seen_ids = db.session.query(BroadcastSeen.broadcast_id).filter(BroadcastSeen.user_id == current_user.id)

    q = Broadcast.query.filter(~Broadcast.id.in_(seen_ids)).order_by(Broadcast.created_at.desc())

    q = q.filter(
        or_(
            Broadcast.target == "all",
            (Broadcast.target == "supervisors") & (current_user.role == "supervisor"),
            (Broadcast.target == "company") & (Broadcast.company_id == current_user.company_id),
            (Broadcast.target == "supervisors_company")
            & (current_user.role == "supervisor")
            & (Broadcast.company_id == current_user.company_id)
        )
    )

    items = [b.to_dict() for b in q.all()]
    return jsonify(items)


# ==========================================================
# 🔹 API: Mark broadcast as seen
# ==========================================================
@bp.route("/mark_seen", methods=["POST"])
@login_required
def mark_seen():
    b_id = request.json.get("broadcast_id")
    if not b_id:
        return jsonify({"error": "broadcast_id required"}), 400

    exists = BroadcastSeen.query.filter_by(broadcast_id=b_id, user_id=current_user.id).first()
    if not exists:
        db.session.add(BroadcastSeen(broadcast_id=b_id, user_id=current_user.id))
        db.session.commit()

    return jsonify({"ok": True})


# ==========================================================
# 🔹 ADMIN: View Broadcasts Page
# ==========================================================
@bp.route("/broadcasts", methods=["GET", "POST"])
@login_required
def view_broadcasts():
    if current_user.role != "admin":
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    # ✅ Optional POST handler (legacy)
    if request.method == "POST":
        message = request.form.get("message")
        if message:
            socketio.emit("new_broadcast", {"message": message}, broadcast=True)
            flash("Broadcast sent to all connected users!", "success")
        return redirect(url_for("broadcasts.view_broadcasts"))

    # ✅ Get all broadcasts
    broadcasts = Broadcast.query.order_by(Broadcast.created_at.desc()).all()

    # ✅ Group by Month > Date
    grouped = defaultdict(lambda: defaultdict(list))
    for b in broadcasts:
        month_key = b.created_at.strftime("%B %Y")
        date_key = b.created_at.strftime("%d %b %Y")
        grouped[month_key][date_key].append({
            "id": b.id,
            "message": b.message,
            "title": b.title,
            "target": b.target,
            "company_name": b.company.name if b.company else None,
            "sender_name": getattr(b.sender, "username", "Admin"),
            "created_at": b.created_at,
            "created_at_display": b.created_at.strftime("%H:%M")
        })

    # ✅ Flatten list for view lookup
    all_broadcasts_flat = [b for month in grouped.values() for date in month.values() for b in date]
    broadcast_ids = [b["id"] for b in all_broadcasts_flat]
    db_broadcasts = Broadcast.query.filter(Broadcast.id.in_(broadcast_ids)).all()
    view_summary = get_broadcast_view_data(db_broadcasts)

    companies = Company.query.order_by(Company.name.asc()).all()

    return render_template(
        "admin/broadcasts.html",
        broadcasts=grouped,
        companies=companies,
        current_time=datetime.utcnow(),
        view_summary=view_summary
    )


# ==========================================================
# 🔹 Delete Broadcast (Admin Only)
# ==========================================================
@bp.route("/delete/<int:id>", methods=["POST"])
@login_required
def delete_broadcast(id):
    # ✅ Ensure only admin can delete
    if current_user.role != "admin":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("broadcasts.view_broadcasts"))

    # ✅ Fetch broadcast
    broadcast = Broadcast.query.get_or_404(id)

    # ✅ Check 10-minute deletion window
    # Use naive datetime comparison
    time_diff = (datetime.utcnow() - broadcast.created_at).total_seconds()

    if time_diff <= 600:  # 600 seconds = 10 minutes
        # ✅ Delete broadcast; all BroadcastSeen entries will be removed automatically via cascade
        db.session.delete(broadcast)
        db.session.commit()

        # ✅ Notify clients via Socket.IO
        socketio.emit("admin_broadcast_update", {})

        flash("Broadcast and all related seen history deleted successfully.", "success")
    else:
        flash("You can only delete a broadcast within 10 minutes of creation.", "warning")

    return redirect(url_for("broadcasts.view_broadcasts"))
# ==========================================================
# 🔹 Helper: View details per broadcast
# ==========================================================
def get_broadcast_view_data(broadcasts):
    view_summary = {}

    for b in broadcasts:
        views = (
            BroadcastSeen.query
            .filter_by(broadcast_id=b.id)
            .join(User, BroadcastSeen.user_id == User.id)
            .join(Company, isouter=True)
            .with_entities(
                User.first_name,
                User.last_name,
                User.username,
                User.role,
                Company.name.label("company_name"),
                BroadcastSeen.seen_at.label("seen_at")
            )
            .order_by(BroadcastSeen.seen_at.desc())
            .all()
        )

        view_summary[b.id] = {
            "count": len(views),
            "details": [
                {
                    "full_name": f"{v.first_name or ''} {v.last_name or ''}".strip(),
                    "username": v.username,
                    "role": v.role,
                    "company": v.company_name or "—",
                    "seen_at": v.seen_at.strftime("%d %b %Y, %H:%M")
                }
                for v in views
            ]
        }

    return view_summary
