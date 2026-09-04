import hashlib
import secrets
from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

class Role:
    SUPER_ADMIN = 'super_admin'
    ADMIN = 'admin'
    TEACHER = 'teacher'
    STUDENT = 'student'
    PARENT = 'parent'

    CHOICES = [
        (SUPER_ADMIN, 'Super Admin / Owner'),
        (ADMIN, 'Administrator / Staff'),
        (TEACHER, 'Teacher'),
        (STUDENT, 'Student'),
        (PARENT, 'Parent')
    ]

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=Role.STUDENT)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_verified = db.Column(db.Boolean, default=True, nullable=False)
    verification_token_hash = db.Column(db.String(128), nullable=True)
    verification_sent_at = db.Column(db.DateTime, nullable=True)
    password_reset_token_hash = db.Column(db.String(128), nullable=True)
    password_reset_expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    teacher_profile = db.relationship('Teacher', backref='user', uselist=False, cascade='all, delete-orphan')
    student_profile = db.relationship('Student', backref='user', uselist=False, cascade='all, delete-orphan')
    parent_profile = db.relationship('Parent', backref='user', uselist=False, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_verification_token(self):
        token = secrets.token_urlsafe(32)
        self.verification_token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        self.verification_sent_at = datetime.utcnow()
        return token

    def verify_email_token(self, token, expiration_minutes=60*24):
        if not token or not self.verification_token_hash:
            return False
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        if self.verification_token_hash != token_hash:
            return False
        if self.verification_sent_at and (datetime.utcnow() - self.verification_sent_at) > timedelta(minutes=expiration_minutes):
            return False
        self.is_verified = True
        self.verification_token_hash = None
        self.verification_sent_at = None
        return True

    def generate_password_reset_token(self, expiration_minutes=60):
        token = secrets.token_urlsafe(32)
        self.password_reset_token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        self.password_reset_expires_at = datetime.utcnow() + timedelta(minutes=expiration_minutes)
        return token

    def verify_password_reset_token(self, token):
        if not token or not self.password_reset_token_hash or not self.password_reset_expires_at:
            return False
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        if self.password_reset_token_hash != token_hash:
            return False
        if datetime.utcnow() > self.password_reset_expires_at:
            return False
        return True

    def clear_password_reset_token(self):
        self.password_reset_token_hash = None
        self.password_reset_expires_at = None

    @classmethod
    def get_super_admin(cls):
        return cls.query.filter_by(role=Role.SUPER_ADMIN).first()

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def is_super_admin(self):
        return self.role == Role.SUPER_ADMIN

    def is_admin(self):
        return self.role in [Role.SUPER_ADMIN, Role.ADMIN]

    def is_teacher(self):
        return self.role == Role.TEACHER

    def is_student(self):
        return self.role == Role.STUDENT

    def is_parent(self):
        return self.role == Role.PARENT

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'is_active': self.is_active,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'

