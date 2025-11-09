from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property
from app import db

# ==========================================================
# COMPANY MODEL
# ==========================================================
class Company(db.Model):
    __tablename__ = 'companies'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    created_by = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship: one company → many users
    users = db.relationship('User', back_populates='company', lazy=True)

    def __repr__(self):
        return f"<Company {self.name}>"


# ==========================================================
# USER MODEL
# ==========================================================
class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True)
    password_hash = db.Column(db.String(512), nullable=False)
    shift = db.Column(db.String(20), nullable=True)
    role = db.Column(db.String(20), nullable=False, default='agent')
    cnic = db.Column(db.String(20), nullable=True)

    # ✅ Company Foreign Key
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'))
    company = db.relationship('Company', back_populates='users')

    # ✅ Salary Field
    salary = db.Column(db.Float, nullable=True, default=0.0)

    # ✅ Status & Metadata
    is_active_db = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ Travel Allowance
    travel_allowance_eligible = db.Column(db.Boolean, default=False)
    travel_allowance_amount = db.Column(db.Integer, nullable=True)

    # ==========================================================
    # 🧾 NEW: Profile Fields (Added for Agent Profile Page)
    # ==========================================================
    father_name = db.Column(db.String(100), nullable=True)
    current_address = db.Column(db.String(255), nullable=True)
    permanent_address = db.Column(db.String(255), nullable=True)

    # Contact Information
    contact_number = db.Column(db.String(20), nullable=True)
    emergency_contact = db.Column(db.String(20), nullable=True)
    whatsapp_number = db.Column(db.String(20), nullable=True)

    # Personal Info
    blood_group = db.Column(db.String(10), nullable=True)
    resume_path = db.Column(db.String(255), nullable=True)  # Path to uploaded CV

    # Profile Pictures
    profile_picture = db.Column(db.String(255), nullable=True)

    # CNIC Details (User)
    cnic_front = db.Column(db.String(255), nullable=True)
    cnic_back = db.Column(db.String(255), nullable=True)

    # CNIC Details (Father/Guardian)
    guardian_cnic_front = db.Column(db.String(255), nullable=True)
    guardian_cnic_back = db.Column(db.String(255), nullable=True)

    # ✅ Locking flag (once saved, cannot be edited unless admin unlocks)
    profile_locked = db.Column(db.Boolean, default=False)

 # --------------------------------------------------
    # Relationships
    # --------------------------------------------------
    penalties = db.relationship('Penalty', backref='user', foreign_keys='Penalty.user_id', lazy=True)
    marked_penalties = db.relationship('Penalty', backref='marker', foreign_keys='Penalty.marked_by', lazy=True)

    clearances = db.relationship('Clearance', backref='user', foreign_keys='Clearance.user_id', lazy=True)
    marked_clearances = db.relationship('Clearance', backref='marker', foreign_keys='Clearance.marked_by', lazy=True)


    # --------------------------------------------------
    # Password Management
    # --------------------------------------------------
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # --------------------------------------------------
    # Flask-Login Compatibility
    # --------------------------------------------------
    @property
    def is_active(self):
        if self.username.lower() == "admin":
            return True
        return self.is_active_db

    @is_active.setter
    def is_active(self, value):
        if self.username.lower() == "admin":
            self.is_active_db = True
        else:
            self.is_active_db = value

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------
    def user_full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()

    def __repr__(self):
        return f"<User {self.username} ({self.role}) - Active: {self.is_active_db}>"
    
    @hybrid_property
    def full_name(self):
        return f"{self.first_name or ''} {self.last_name or ''}".strip()


# ==========================================================
# ATTENDANCE MODEL
# ==========================================================
class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    is_late = db.Column(db.Boolean, default=False)
    bonus = db.Column(db.Float, default=0.0)
    penalty = db.Column(db.Float, default=0.0)
    marked_by = db.Column(
        db.Integer,
        db.ForeignKey('users.id', name='fk_attendance_marked_by_users'),
        nullable=True
    )

    user = db.relationship('User', foreign_keys=[user_id], backref='attendance_records', lazy=True)
    marker = db.relationship('User', foreign_keys=[marked_by], backref='marked_attendances', lazy=True)


# ==========================================================
# INCREMENT MODEL
# ==========================================================
class Increment(db.Model):
    __tablename__ = 'increments'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    previous_salary = db.Column(db.Float, nullable=False, default=0.0)
    increment_amount = db.Column(db.Float, nullable=False, default=0.0)
    new_salary = db.Column(db.Float, nullable=False, default=0.0)
    reason = db.Column(db.String(255))
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='increments', lazy=True)

    def __repr__(self):
        return f"<Increment User={self.user_id} +{self.increment_amount}>"


# ==========================================================
# BROADCAST MODEL
# ==========================================================
class Broadcast(db.Model):
    __tablename__ = 'broadcasts'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=True)
    target = db.Column(db.String(32), nullable=False)   # 'all', 'company', 'supervisors'
    title = db.Column(db.String(200), nullable=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id])
    company = db.relationship('Company', foreign_keys=[company_id])

    # ✅ Cascade delete ensures related BroadcastSeen entries are auto-deleted
    seen_by = db.relationship(
        'BroadcastSeen',
        back_populates='broadcast',
        cascade='all, delete-orphan',
        passive_deletes=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_name": self.sender.full_name or self.sender.username,
            "company_id": self.company_id,
            "company_name": self.company.name if self.company else None,
            "target": self.target,
            "title": self.title,
            "message": self.message,
            "created_at": self.created_at.isoformat()
        }


    def __repr__(self):
        return f"<Broadcast id={self.id} target={self.target}>"

# ==========================================================
# BROADCAST SEEN (which users have seen which broadcast)
# ==========================================================
class BroadcastSeen(db.Model):
    __tablename__ = 'broadcast_seen'
    id = db.Column(db.Integer, primary_key=True)

    # ✅ Add ondelete='CASCADE' for automatic cleanup
    broadcast_id = db.Column(
        db.Integer,
        db.ForeignKey('broadcasts.id', ondelete='CASCADE'),
        nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seen_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ✅ Back-populate relationship
    broadcast = db.relationship('Broadcast', back_populates='seen_by')
    user = db.relationship('User', foreign_keys=[user_id], lazy=True)

    __table_args__ = (
        db.UniqueConstraint('broadcast_id', 'user_id', name='uq_broadcast_user_seen'),
    )

    def __repr__(self):
        return f"<BroadcastSeen b={self.broadcast_id} u={self.user_id}>"


# ==========================================================
# PENALTY MODEL
# ==========================================================
class Penalty(db.Model):
    __tablename__ = 'penalties'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Penalty user={self.user_id} amount={self.amount} reason={self.reason}>"


# ==========================================================
# CLEARANCE MODEL
# ==========================================================
class Clearance(db.Model):
    __tablename__ = 'clearances'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.String(255))
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Clearance user={self.user_id} amount={self.amount} reason={self.reason}>"