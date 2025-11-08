from flask import Blueprint, render_template, redirect, url_for, abort, request, flash, current_app
from collections import defaultdict
from flask import jsonify
from flask_login import login_required, current_user
import socketio
from sqlalchemy import or_
from app.models import Broadcast, Penalty, User, Attendance, Increment, db, Clearance
from datetime import datetime, date
import calendar
from werkzeug.utils import secure_filename
import os
from werkzeug.security import check_password_hash, generate_password_hash
from app.routes.broadcasts import get_broadcast_view_data
from app.utils.uploads import ALLOWED_DOC_EXT, ALLOWED_IMAGE_EXT, remove_user_file, save_user_file
from datetime import datetime, date
import pytz


# Blueprint setup
supervisor_bp = Blueprint('supervisor', __name__, url_prefix='/supervisor')

@supervisor_bp.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    shift = current_user.shift

    # All users in supervisor's company with same shift
    team_members = User.query.filter_by(company_id=current_user.company_id, shift=shift).all()

    # Attendance details for today
    today_records = Attendance.query.filter(
        Attendance.date == today,
        Attendance.user_id.in_([u.id for u in team_members])
    ).all()

    presents = sum(1 for a in today_records if a.status == 'Present')
    lates = sum(1 for a in today_records if a.is_late)
    absents = sum(1 for a in today_records if a.status == 'Absent')
    offs = sum(1 for a in today_records if a.status == 'Off')

    performance = round((presents / len(team_members) * 100), 1) if team_members else 0

    stats = {
        "team_members": len(team_members),
        "presents": presents,
        "lates": lates,
        "absents": absents,
        "offs":offs,
        "performance": performance
    }

    return render_template(
        'supervisor/dashboard.html',
        stats=stats,
        current_date=today
    )


@supervisor_bp.route('/attendance')
@login_required
def attendance():
    return render_template('supervisor/attendance.html')


# -------------------------------
# Team Members Page
# -------------------------------
@supervisor_bp.route('/team-members')
@login_required
def team_members():
    if current_user.role != 'supervisor':
        abort(403)

    # Fetch all users in same company and shift
    users = User.query.filter_by(
        company_id=current_user.company_id,
        shift=current_user.shift
    ).all()

    # --- Build attendance summary for each user ---
    attendance_summary = {}
    for user in users:
        records = Attendance.query.filter_by(user_id=user.id).all()

        presents = sum(1 for r in records if r.status == 'Present')
        lates = sum(1 for r in records if r.status == 'Late')
        offs = sum(1 for r in records if r.status == 'Off')
        absents = sum(1 for r in records if r.status == 'Absent')
        penalties = sum((r.penalty or 0) for r in records)
        bonuses = sum((r.bonus or 0) for r in records)

        per_day_salary = (user.salary or 0) / 30  # Assume 30 days in a month
        calculated_salary = (presents + offs) * per_day_salary + bonuses - penalties

        attendance_summary[user.id] = {
            'presents': presents,
            'lates': lates,
            'offs': offs,
            'absents': absents,
            'penalties': penalties,
            'bonuses': bonuses,
            'calculated_salary': calculated_salary
        }

    # ✅ Pass both users and attendance_summary to the template
    return render_template(
        'supervisor/team_members.html',
        users=users,
        attendance_summary=attendance_summary
    )



# -------------------------------
# 🔹 User Details / Monthly Report
# -------------------------------
@supervisor_bp.route('/user/<int:user_id>')
@login_required
def user_details(user_id):
    if current_user.role != 'supervisor':
        abort(403)

    from datetime import datetime
    import calendar

    # Fetch user within same company & shift
    user = User.query.filter_by(
        id=user_id,
        company_id=current_user.company_id,
        shift=current_user.shift
    ).first_or_404()

    # ---- Month selection (default: current month)
    month_str = request.args.get("month")
    if month_str:
        try:
            selected_month = datetime.strptime(month_str, "%Y-%m")
        except ValueError:
            selected_month = datetime.now()
    else:
        selected_month = datetime.now()

    year = selected_month.year
    month = selected_month.month
    total_days = calendar.monthrange(year, month)[1]

    start_date = datetime(year, month, 1)
    end_date = datetime(year, month, total_days)

    # ---- Fetch Attendance for this month
    records = Attendance.query.filter(
        Attendance.user_id == user.id,
        Attendance.date.between(start_date, end_date)
    ).all()

    presents = sum(1 for r in records if r.status.lower() == 'present')
    absents = sum(1 for r in records if r.status.lower() == 'absent')
    lates = sum(1 for r in records if r.is_late)
    late_penalty = lates * 400
    paid_offs = 4

    # ---- Penalties from penalties table (for this month)
    penalties = (
        Penalty.query.filter(
            Penalty.user_id == user.id,
            Penalty.created_at.between(start_date, end_date)
        ).all()
    )
    total_penalties = sum(p.amount for p in penalties)

    # ---- Bonuses (from increments table)
    total_bonuses = sum(i.increment_amount for i in user.increments if i.increment_amount > 0)

    # ---- Travel Allowance
    travel_allowance = 5000 if user.travel_allowance_eligible else 0

    # ---- Salary Breakdown
    per_day_salary = (user.salary or 0) / total_days
    salary_for_presents = per_day_salary * presents
    salary_for_offs = per_day_salary * paid_offs

    net_salary = (
        salary_for_presents
        - late_penalty
        - total_penalties
        + salary_for_offs
        + total_bonuses
        + travel_allowance
    )

    # ---- Attendance dates
    absent_dates = [r.date for r in records if r.status.lower() == 'absent']
    off_dates = []  # Future enhancement

    # ---- Profile Completion %
    filled_fields = sum(
        1 for f in [
            user.first_name, user.last_name, user.father_name, user.contact_number,
            user.current_address, user.permanent_address, user.whatsapp_number,
            user.blood_group, user.profile_picture, user.cnic_front, user.cnic_back
        ] if f
    )
    total_fields = 10
    profile_completion = int((filled_fields / total_fields) * 100)

    return render_template(
        'supervisor/user_details.html',
        user=user,
        presents=presents,
        lates=lates,
        absents=absents,
        late_penalty=late_penalty,
        penalties=total_penalties,
        bonuses=total_bonuses,
        travel_allowance=travel_allowance,
        net_salary=net_salary,
        per_day_salary=per_day_salary,
        salary_for_presents=salary_for_presents,
        salary_for_offs=salary_for_offs,
        total_days=total_days,
        absent_dates=absent_dates,
        off_dates=off_dates,
        penalties_list=penalties,
        month_name=selected_month.strftime("%B %Y"),
        month_value=selected_month.strftime("%Y-%m"),
        profile_completion=profile_completion
    )

# -----------------------------
# Supervisor Attendance Dashboard (Enhanced with Penalty Counts)
# -----------------------------
@supervisor_bp.route('/attendance_dashboard', methods=['GET'])
@login_required
def attendance_dashboard():
    from collections import defaultdict
    from datetime import date, datetime
    from sqlalchemy import extract

    month = request.args.get('month', date.today().strftime('%Y-%m'))
    shift = request.args.get('shift', current_user.shift)

    # Extract numeric year/month for filtering
    year, month_num = map(int, month.split('-'))

    # Fetch all users in this supervisor's company + shift
    users = User.query.filter_by(company_id=current_user.company_id, shift=shift).all()
    user_ids = [u.id for u in users]

    # --- Attendance Records (for selected month) ---
    records = (
        Attendance.query
        .join(User, Attendance.user_id == User.id)
        .filter(User.company_id == current_user.company_id)
        .filter(User.shift == shift)
        .filter(extract('year', Attendance.date) == year)
        .filter(extract('month', Attendance.date) == month_num)
        .order_by(Attendance.date.desc(), Attendance.time.desc())
        .all()
    )

    # --- Penalties (for same users and month) ---
    penalties = (
        Penalty.query
        .filter(Penalty.user_id.in_(user_ids))
        .filter(extract('year', Penalty.created_at) == year)
        .filter(extract('month', Penalty.created_at) == month_num)
        .order_by(Penalty.created_at.desc())
        .all()
    )

    # Group penalties by (user_id, date)
    penalties_by_user_date = defaultdict(list)
    for p in penalties:
        p_date = p.created_at.date()
        penalties_by_user_date[(p.user_id, p_date)].append({
            "amount": p.amount,
            "reason": p.reason or "No reason given",
            "marked_by": f"{p.marker.first_name} {p.marker.last_name}" if p.marker else "Unknown"
        })

    # --- Group attendance by date ---
    grouped = defaultdict(list)
    for r in records:
        grouped[r.date].append(r)

    attendance_by_date = []
    for dt in sorted(grouped.keys(), reverse=True):
        day_records = grouped[dt]
        presents = sum(1 for r in day_records if r.status == 'Present')
        lates = sum(1 for r in day_records if r.status == 'Late')
        offs = sum(1 for r in day_records if r.status == 'Off')
        absents = sum(1 for r in day_records if r.status == 'Absent')
        bonuses = sum((r.bonus or 0) for r in day_records)

        # --- Calculate penalties per date ---
        total_penalty_amount = 0
        total_penalty_count = 0

        for r in day_records:
            penalty_details = penalties_by_user_date.get((r.user_id, dt), [])
            r.penalty_details = penalty_details
            if penalty_details:
                total_penalty_count += len(penalty_details)
                total_penalty_amount += sum(p["amount"] for p in penalty_details)

        markers = sorted({r.marker.user_full_name() if r.marker else "—" for r in day_records})

        attendance_by_date.append({
            "date": dt,
            "display_date": dt.strftime("%Y-%m-%d"),
            "records": day_records,
            "counts": {
                "presents": presents,
                "lates": lates,
                "offs": offs,
                "absents": absents,
                "bonuses": bonuses,
                "penalties": total_penalty_amount,
                "penalty_count": total_penalty_count,  # ✅ new field
            },
            "marked_by": ", ".join(markers),
            "shift": shift,
        })

    # --- Monthly summary per user ---
    monthly_summary = []
    for u in users:
        user_records = [r for r in records if r.user_id == u.id]

        total_present = sum(1 for r in user_records if r.status == 'Present')
        total_late = sum(1 for r in user_records if r.status == 'Late')
        total_absent = sum(1 for r in user_records if r.status == 'Absent')
        total_off = sum(1 for r in user_records if r.status == 'Off')
        total_bonus = sum((r.bonus or 0) for r in user_records)

        # --- Calculate penalties for this user (from grouped penalties) ---
        user_penalties = [
            p for key, plist in penalties_by_user_date.items()
            if key[0] == u.id for p in plist
        ]
        total_penalty = sum(p["amount"] for p in user_penalties)

        calculated_salary = (u.salary or 0) + total_bonus - total_penalty

        user_daily_records = sorted(user_records, key=lambda r: r.date, reverse=True)

        monthly_summary.append({
            "user": u,
            "present": total_present,
            "late": total_late,
            "absent": total_absent,
            "off": total_off,
            "bonus": total_bonus,
            "penalty": total_penalty,
            "penalty_count": len(user_penalties),  # ✅ new field
            "base_salary": u.salary or 0,
            "final_salary": calculated_salary,
            "attendance_records": user_daily_records,
        })

    monthly_summary.sort(key=lambda x: x["user"].user_full_name().lower())

    # --- Recent Clearances ---
    clearances = Clearance.query.filter(
        Clearance.user.has(company_id=current_user.company_id)
    ).order_by(Clearance.date_added.desc()).limit(10).all()

    return render_template(
        "supervisor/attendance_dashboard.html",
        attendance_by_date=attendance_by_date,
        month=month,
        shift=shift,
        monthly_summary=monthly_summary,
        shifts=["morning", "evening", "night"],
        current_date=date.today(),
        clearances=clearances,
    )


# ✅ Route: Mark Attendance
@supervisor_bp.route('/mark_attendance', methods=['GET', 'POST'])
@login_required
def mark_attendance():


    pk_tz = pytz.timezone("Asia/Karachi")
    now_pk = datetime.now(pk_tz)
    today = now_pk.date()

    shift = request.args.get('shift', 'morning')
    search = request.args.get('search', '').strip()

    if current_user.role != 'supervisor':
        flash("Access denied.", "danger")
        return redirect(url_for('auth.login'))

    query = User.query.filter(
        User.company_id == current_user.company_id,
        User.role.in_(['agent', 'supervisor']),
        User.shift == shift
    )

    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) |
            (User.first_name.ilike(f"%{search}%")) |
            (User.last_name.ilike(f"%{search}%"))
        )

    users = query.all()

    if request.method == 'POST':
        for user in users:
            status = request.form.get(f'status_{user.id}')
            if not status:
                continue

            attendance = Attendance.query.filter_by(user_id=user.id, date=today).first()
            if not attendance:
                attendance = Attendance(
                    user_id=user.id,
                    date=today,
                    time=now_pk.time(),
                    marked_by=current_user.id
                )
                db.session.add(attendance)

            attendance.status = status
            attendance.is_late = (status == 'Late')

        db.session.commit()
        flash("Attendance saved successfully!", "success")
        return redirect(url_for('supervisor.mark_attendance', shift=shift, search=search))

    clearances = Clearance.query.order_by(Clearance.date_added.desc()).limit(10).all()
    return render_template('supervisor/mark_attendance.html', users=users, shift=shift, search=search, clearances=clearances)




@supervisor_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = current_user

    if request.method == "POST":
        # Check lock status
        if user.profile_locked:
            flash("Profile is locked and cannot be edited. Contact admin to unlock.", "warning")
            return redirect(url_for('supervisor.profile'))

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
            return redirect(url_for('supervisor.profile'))

        # ✅ Lock profile after save
        user.profile_locked = True
        db.session.commit()
        flash("Profile updated and locked successfully.", "success")
        return redirect(url_for('supervisor.profile'))

    # ✅ Always return something on GET
    return render_template('supervisor/profile.html', user=user)



@supervisor_bp.route('/reset_password', methods=['POST'])
@login_required
def reset_password_alias():
    return redirect(url_for('supervisor.profile_pass'))


@supervisor_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def profile_pass():
    """supervisor password reset route"""
    if current_user.role != 'supervisor':
        flash("Unauthorized access.", "danger")
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_new_password = request.form.get('confirm_new_password')

        # ✅ Verify current password
        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for('supervisor.profile_pass'))

        # ✅ Check if new passwords match
        if new_password != confirm_new_password:
            flash("New passwords do not match.", "warning")
            return redirect(url_for('supervisor.profile_pass'))

        # ✅ Prevent using same password again
        if current_user.check_password(new_password):
            flash("New password cannot be the same as your current one.", "warning")
            return redirect(url_for('supervisor.profile_pass'))

        # ✅ Update password using model’s method
        current_user.set_password(new_password)
        db.session.commit()

        flash("✅ Password updated successfully!", "success")
        return redirect(url_for('supervisor.profile_pass'))

    return render_template('supervisor/profile_pass.html')



@supervisor_bp.route("/reports")
@login_required
def supervisor_reports():
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

    #1 group attendance by month
    records = Attendance.query.filter_by(user_id=user.id).all()
    from collections import defaultdict
    from calendar import month_name
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

    for (year, month), recs in grouped.items():
        total_presents = sum(1 for r in recs if r.status == "Present")
        total_lates = sum(1 for r in recs if r.status == "Late")
        total_offs = sum(1 for r in recs if r.status == "Off")
        total_absents = sum(1 for r in recs if r.status == "Absent")
        total_bonus = sum(r.bonus for r in recs)
        total_penalty = 0 # we'll accumulate dynamically

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
                
        # salary calc
        final_salary = (
            user.salary
            + (user.travel_allowance_amount or 0)
            + total_bonus
            - total_penalty
            - (total_lates * 400)
            - ((max(total_absents - 4, 0)) * (user.salary / 30))
        )

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

        # accumulate totals
        totals["total_presents"] = total_presents
        totals["total_lates"] = total_lates
        totals["total_offs"] = total_offs
        totals["total_absents"] = total_absents
        totals["total_bonus"] = total_bonus
        totals["total_penalty"] = total_penalty
        totals["final_salary"] = final_salary

    return render_template("supervisor/reports.html", user=user, monthly_reports=monthly_reports, totals=totals)


@supervisor_bp.route('/salaries')
@login_required
def salaries():
    return render_template('supervisor/salaries.html')

@supervisor_bp.route('/broadcast')
@login_required
def broadcast():
    return render_template('supervisor/broadcasts.html')


# ==========================================================
# 🔹 SUPERVISOR: Create Broadcast (to shifts or agents)
# ==========================================================
@supervisor_bp.route("/supervisor/create", methods=["POST"])
@login_required
def supervisor_create_broadcast():
    if current_user.role != "supervisor":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("auth.login"))

    title = request.form.get("title", "").strip()
    message = request.form.get("message", "").strip()
    target_type = request.form.get("target_type", "shift").strip()  # "shift" or "agent"
    shift = request.form.get("shift", "").strip()
    agent_ids = request.form.getlist("agent_ids")  # multiple agent IDs possible
    send_to_all_shifts = request.form.get("send_to_all_shifts") == "true"

    if not message:
        flash("Message is required.", "danger")
        return redirect(request.referrer or url_for("supervisor.broadcasts"))

    # ✅ Determine company context
    company_id = current_user.company_id
    if not company_id:
        flash("No associated company found.", "danger")
        return redirect(request.referrer or url_for("supervisor.broadcasts"))

    # ✅ Create broadcast entry
    b = Broadcast(
        sender_id=current_user.id,
        title=title or None,
        message=message,
        target="shift" if not send_to_all_shifts else "company",
        company_id=company_id
    )
    db.session.add(b)
    db.session.commit()

    payload = b.to_dict()

    # ✅ Determine recipients
    if send_to_all_shifts:
        recipients_query = User.query.filter(User.company_id == company_id)
    elif target_type == "shift" and shift:
        recipients_query = User.query.filter(
            User.company_id == company_id,
            User.shift == shift
        )
    elif target_type == "agent" and agent_ids:
        recipients_query = User.query.filter(User.id.in_(agent_ids))
    else:
        recipients_query = User.query.filter(User.company_id == company_id)

    recipient_ids = [r.id for r in recipients_query.with_entities(User.id).all()]

    # ✅ Emit broadcast to recipients
    for uid in recipient_ids:
        socketio.emit("new_broadcast", payload, room=f"user_{uid}")

    socketio.emit("admin_broadcast_update", payload)
    flash("Broadcast sent successfully!", "success")

    return redirect(url_for("supervisor.broadcasts"))


# ==========================================================
# 🔹 SUPERVISOR: View Broadcasts
# ==========================================================
@supervisor_bp.route("/supervisor/broadcasts")
@login_required
def supervisor_broadcasts():
    if current_user.role != "supervisor":
        flash("Access denied.", "danger")
        return redirect(url_for("auth.login"))

    # ✅ Fetch broadcasts created by this supervisor or within their company
    broadcasts = (
        Broadcast.query
        .filter(
            Broadcast.company_id == current_user.company_id,
            Broadcast.sender_id == current_user.id
        )
        .order_by(Broadcast.created_at.desc())
        .all()
    )

    grouped = defaultdict(lambda: defaultdict(list))
    for b in broadcasts:
        month_key = b.created_at.strftime("%B %Y")
        date_key = b.created_at.strftime("%d %b %Y")
        grouped[month_key][date_key].append(b)

    db_broadcasts = broadcasts
    view_summary = get_broadcast_view_data(db_broadcasts)

    return render_template(
        "supervisor/broadcasts.html",
        broadcasts=grouped,
        current_time=datetime.utcnow(),
        view_summary=view_summary
    )


@supervisor_bp.route("/add_penalty", methods=["POST"])
@login_required
def add_penalty():
    """Supervisor adds a penalty to an agent (same company only)."""
    if current_user.role != "supervisor":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    agent_id = data.get("agent_id")
    amount = data.get("amount")
    reason = data.get("reason")

    # ✅ Validate fields
    if not all([agent_id, amount, reason]):
        return jsonify({"error": "All fields are required."}), 400

    # ✅ Verify agent belongs to the same company
    agent = User.query.filter(
    User.id == agent_id,
    User.company_id == current_user.company_id,
    User.role.in_(["agent", "supervisor"])
        ).first()

    if not agent:
        return jsonify({"error": "Agent not found or not in your company."}), 404

    # ✅ Save penalty
    penalty = Penalty(
        user_id=agent.id,
        amount=float(amount),
        reason=reason,
        marked_by=current_user.id
    )
    db.session.add(penalty)
    db.session.commit()

    return jsonify({"message": f"Penalty of {amount} added to {agent.full_name}."}), 200


@supervisor_bp.route("/add_clearance", methods=["POST"])
@login_required
def add_clearance():
    """Supervisor adds a clearance record for an agent."""
    if current_user.role != "supervisor":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    agent_id = data.get("agent_id")
    amount = data.get("amount")
    reason = data.get("reason")

    if not all([agent_id, amount, reason]):
        return jsonify({"error": "All fields are required."}), 400

    agent = User.query.filter(
    User.id == agent_id,
    User.company_id == current_user.company_id,
    User.role.in_(["agent", "supervisor"])
        ).first()

    if not agent:
        return jsonify({"error": "Agent not found or not in your company."}), 404

    clearance = Clearance(
        user_id=agent.id,
        amount=float(amount),
        reason=reason,
        marked_by=current_user.id
    )
    db.session.add(clearance)
    db.session.commit()

    return jsonify({"message": f"Clearance of {amount} added for {agent.full_name}."}), 200


# ------------------------------------------------------
# AJAX: Live search agents (only those in supervisor's company)
# ------------------------------------------------------
@supervisor_bp.route("/search_agents")
@login_required
def search_agents():
    if current_user.role != "supervisor":
        return jsonify([])

    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    agents = (
    User.query
    .filter(
        User.company_id == current_user.company_id,
        User.role.in_(["agent", "supervisor"]),
        or_(
            User.first_name.ilike(f"%{query}%"),
            User.last_name.ilike(f"%{query}%"),
            User.username.ilike(f"%{query}%"),
        )
    )
    .limit(10)
    .all()
)


    results = [
        {"id": a.id, "name": a.full_name, "username": a.username, "salary": a.salary}
        for a in agents
    ]
    return jsonify(results)