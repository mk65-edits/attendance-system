from collections import defaultdict
from flask import Blueprint, jsonify, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
import socketio
from werkzeug.utils import secure_filename
import os
from app.models import Broadcast, Penalty
from app.models import Broadcast, BroadcastSeen, User, Company
from app.models import Attendance
from datetime import datetime, date
from app import db
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import User
from app.routes.broadcasts import get_broadcast_view_data
from app.utils.uploads import ALLOWED_DOC_EXT, ALLOWED_IMAGE_EXT, remove_user_file, save_user_file
import calendar





UPLOAD_FOLDER = 'static/uploads'



# Blueprint setup
agent_bp = Blueprint('agent', __name__, url_prefix='/agent')

# ==========================================================
# 🧭 AGENT DASHBOARD
# ==========================================================
@agent_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'agent':
        return "Unauthorized Access", 403

    today = datetime.today()
    month_start = datetime(today.year, today.month, 1)
    month_end = datetime(today.year, today.month, calendar.monthrange(today.year, today.month)[1])

    # ✅ Fetch attendance records for this month
    attendance_records = Attendance.query.filter(
        Attendance.user_id == current_user.id,
        Attendance.date >= month_start.date(),
        Attendance.date <= month_end.date()
    ).all()

    # Counters
    total_presents = sum(1 for a in attendance_records if a.status.lower() == "present")
    total_lates = sum(1 for a in attendance_records if a.is_late)
    total_absents = sum(1 for a in attendance_records if a.status.lower() == "absent")
    total_offs = sum(1 for a in attendance_records if a.status == "Off")

    # ✅ Calculate performance (custom logic)
    total_days = len(attendance_records)
    if total_days > 0:
        performance = round(((total_presents + (0.5 * total_lates)) / total_days) * 100, 2)
    else:
        performance = 0.0

    # ✅ Prepare context for template
    dashboard_data = {
        "month_name": today.strftime("%B %Y"),
        "total_presents": total_presents,
        "total_lates": total_lates,
        "total_absents": total_absents,
        "total_offs": total_offs,
        "performance": performance,
        "joining_date": current_user.created_at.strftime("%d %B %Y") if current_user.created_at else "N/A"
    }

    return render_template("agent/dashboard.html", user=current_user, data=dashboard_data, current_date=datetime.today())
# app/routes/agent_routes.py

@agent_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user

    if request.method == "POST":
        # Check lock status
        if user.profile_locked:
            flash("Profile is locked and cannot be edited. Contact admin to unlock.", "warning")
            return redirect(url_for('agent.profile'))

        # Textual fields
        user.father_name = request.form.get('father_name', '').strip() or user.father_name
        user.current_address = request.form.get('current_address', '').strip() or user.current_address
        user.permanent_address = request.form.get('permanent_address', '').strip() or user.permanent_address
        user.contact_number = request.form.get('contact_number', '').strip() or user.contact_number
        user.emergency_contact = request.form.get('emergency_contact', '').strip() or user.emergency_contact
        user.whatsapp_number = request.form.get('whatsapp_number', '').strip() or user.whatsapp_number
        user.blood_group = request.form.get('blood_group', '').strip() or user.blood_group
        user.cnic = request.form.get('cnic', '').strip() or user.cnic

        # Handle uploads
        try:
            uploads = {
                    "profile_picture": ("profile_pic", ALLOWED_IMAGE_EXT),
                    "cnic_front": ("cnic_front", ALLOWED_IMAGE_EXT),
                    "cnic_back": ("cnic_back", ALLOWED_IMAGE_EXT),
                    "guardian_cnic_front": ("guardian_cnic_front", ALLOWED_IMAGE_EXT),
                    "guardian_cnic_back": ("guardian_cnic_back", ALLOWED_IMAGE_EXT),
                    "resume_path": ("resume", ALLOWED_DOC_EXT),
            }

            for field, (prefix, allowed) in uploads.items():
                file = request.files.get(field)
                if file and file.filename:
                    old_file = getattr(user, field, None)
                    if old_file:
                        remove_user_file(old_file)
                    new_path = save_user_file(file, user, prefix, allowed)
                    setattr(user, field, new_path)

        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for('agent.profile'))

        # ✅ Lock profile after save
        user.profile_locked = True
        db.session.commit()

        flash("Profile updated and locked.", "success")
        return redirect(url_for('agent.profile'))

    # GET
    return render_template('agent/profile.html', user=user)

@agent_bp.route('/reset_password', methods=['POST'])
@login_required
def reset_password_alias():
    return redirect(url_for('agent.profile_pass'))


@agent_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def profile_pass():
    """Agent password reset route"""
    if current_user.role != 'agent':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_new_password = request.form.get('confirm_new_password')

        # ✅ Verify current password
        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for('agent.profile_pass'))

        # ✅ Check if new passwords match
        if new_password != confirm_new_password:
            flash("New passwords do not match.", "warning")
            return redirect(url_for('agent.profile_pass'))

        # ✅ Prevent using same password again
        if current_user.check_password(new_password):
            flash("New password cannot be the same as your current one.", "warning")
            return redirect(url_for('agent.profile_pass'))

        # ✅ Update password using model’s method
        current_user.set_password(new_password)
        db.session.commit()

        flash("✅ Password updated successfully!", "success")
        return redirect(url_for('agent.profile'))

    return render_template('agent/profile_pass.html')


@agent_bp.route("/reports")
@login_required
def agent_reports():
    from collections import defaultdict
    from calendar import month_name
    from datetime import datetime

    user = current_user
    monthly_reports = []
    totals = {
        "total_presents": 0,
        "total_lates": 0,
        "total_offs": 0,
        "total_absents": 0,
        "total_bonus": 0,
        "total_penalty": 0,
        "final_salary": 0
    }

    # ==========================================================
    # 1️⃣ Fetch and group attendance records by month
    # ==========================================================
    records = Attendance.query.filter_by(user_id=user.id).all()
    grouped = defaultdict(list)
    for r in records:
        grouped[(r.date.year, r.date.month)].append(r)

    # ==========================================================
    # 2️⃣ Fetch penalties and group them by DATE only
    # ==========================================================
    penalties = (
        Penalty.query
        .filter_by(user_id=user.id)
        .order_by(Penalty.created_at.desc())
        .all()
    )

    penalties_by_date = defaultdict(list)
    for p in penalties:
        penalties_by_date[p.created_at.date()].append(p)

    # ==========================================================
    # 3️⃣ Build monthly reports
    # ==========================================================
    for (year, month), recs in grouped.items():
        total_presents = sum(1 for r in recs if r.status == "Present")
        total_lates = sum(1 for r in recs if r.status == "Late")
        total_offs = sum(1 for r in recs if r.status == "Off")
        total_absents = sum(1 for r in recs if r.status == "Absent")
        total_bonus = sum(r.bonus for r in recs)
        total_penalty = 0  # we'll accumulate dynamically

        # ----------------------------------------------------------
        # 🔍 Attach all penalties that match the same date
        # ----------------------------------------------------------
        for r in recs:
            same_day_penalties = penalties_by_date.get(r.date, [])
            if same_day_penalties:
                r.penalty_details = [
                    {
                        "amount": p.amount,
                        "reason": p.reason,
                        "added_by": f"{p.marker.first_name} {p.marker.last_name}" if p.marker else "Unknown"
                    }
                    for p in same_day_penalties
                ]
                # calculate daily penalty total
                r.penalty = sum(p.amount for p in same_day_penalties)
                total_penalty += r.penalty
            else:
                r.penalty_details = []
                r.penalty = 0

        # ----------------------------------------------------------
        # 💰 Salary calculation
        # ----------------------------------------------------------
        final_salary = (
            user.salary
            + (user.travel_allowance_amount or 0)
            + total_bonus
            - total_penalty
            - (total_lates * 400)
            - ((max(total_absents - 4, 0)) * (user.salary / 30))
        )

        # ----------------------------------------------------------
        # 📊 Add monthly summary
        # ----------------------------------------------------------
        monthly_reports.append({
            "month_name": f"{month_name[month]} {year}",
            "total_presents": total_presents,
            "total_lates": total_lates,
            "total_offs": total_offs,
            "total_absents": total_absents,
            "total_bonus": total_bonus,
            "total_penalty": total_penalty,
            "final_salary": round(final_salary, 2),
            "daily_records": recs
        })

        # ----------------------------------------------------------
        # 📈 Accumulate overall totals
        # ----------------------------------------------------------
        totals["total_presents"] = total_presents
        totals["total_lates"] = total_lates
        totals["total_offs"] = total_offs
        totals["total_absents"] = total_absents
        totals["total_bonus"] = total_bonus
        totals["total_penalty"] = total_penalty
        totals["final_salary"] = final_salary

    # ==========================================================
    # ✅ Render report page
    # ==========================================================
    return render_template(
        "agent/reports.html",
        user=user,
        monthly_reports=monthly_reports,
        totals=totals
    )


@agent_bp.route('/salaries')
@login_required
def salaries():
    return render_template('agent/salaries.html')

@agent_bp.route("/broadcasts", methods=["GET"])
@login_required
def view_broadcasts():
    if current_user.role != "agent":
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    # Get all broadcasts in descending order
    broadcasts = Broadcast.query.order_by(Broadcast.created_at.desc()).all()
 
        

    # Flattened list grouped by date only
    grouped_by_date = defaultdict(list)
    for b in broadcasts:
        date_key = b.created_at.strftime("%d %b %Y")
        grouped_by_date[date_key].append({
            "id": b.id,
            "title": b.title,
            "message": b.message,
            "target": b.target,
            "company_name": b.company.name if b.company else None,
            "sender_name": b.sender.full_name if b.sender else "Admin",
            "created_at": b.created_at
        })

    # Prepare view summary (counts & details)
    view_summary = get_broadcast_view_data(broadcasts)

    return render_template(
        "agent/broadcasts.html",
        broadcasts=grouped_by_date,
        current_user=current_user,
        view_summary=view_summary
    )


# ==========================================================
# 🔹 Agent: Mark Broadcast as Read
# ==========================================================
# ==========================================================
# 🔹 Agent: Mark Broadcast as Read
# ==========================================================
@agent_bp.route("/broadcasts/mark_read/<int:broadcast_id>", methods=["POST"])
@login_required
def mark_broadcast_read(broadcast_id):
    if current_user.role != "agent":
        return {"status": "error", "message": "Access denied"}, 403

    # ✅ Check if this user has already seen it
    seen = BroadcastSeen.query.filter_by(
        broadcast_id=broadcast_id,
        user_id=current_user.id
    ).first()

    if not seen:
        # ✅ Create a new seen record
        seen = BroadcastSeen(
            broadcast_id=broadcast_id,
            user_id=current_user.id
        )
        db.session.add(seen)
        db.session.commit()
    else:
        # ✅ Update seen_at if user clicks again (optional)
        seen.seen_at = datetime.utcnow()
        db.session.commit()

    # ✅ Return the timestamp for frontend display
    return {
        "status": "success",
        "seen_at": seen.seen_at.strftime("%d %b, %I:%M %p")
    }
