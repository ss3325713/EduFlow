from datetime import datetime
from app.extensions import db

class InstituteSettings(db.Model):
    __tablename__ = 'institute_settings'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, default='EduFlow Academy')
    tagline = db.Column(db.String(256), default='Excellence in Education & Coaching')
    logo_url = db.Column(db.String(256), nullable=True)
    phone = db.Column(db.String(32), default='+1 (800) 555-EDU1')
    email = db.Column(db.String(128), default='contact@eduflow.academy')
    address = db.Column(db.Text, default='100 Learning Way, Tech Park, Suite 500')
    academic_session = db.Column(db.String(32), default='2026-2027')
    country = db.Column(db.String(64), default='United States')
    currency = db.Column(db.String(8), default='$')
    timezone = db.Column(db.String(64), default='UTC')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_settings(cls):
        try:
            settings = cls.query.first()
        except Exception:
            db.session.rollback()
            try:
                with db.engine.connect() as conn:
                    conn.execute(db.text("ALTER TABLE institute_settings ADD COLUMN country VARCHAR(64) DEFAULT 'United States'"))
                    conn.commit()
                settings = cls.query.first()
            except Exception:
                db.session.rollback()
                db.create_all()
                settings = cls.query.first()

        if not settings:
            settings = cls(name='EduFlow Academy', country='United States')
            db.session.add(settings)
            db.session.commit()
        return settings

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'tagline': self.tagline,
            'logo_url': self.logo_url,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'academic_session': self.academic_session,
            'country': self.country,
            'currency': self.currency,
            'timezone': self.timezone
        }

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    action = db.Column(db.String(64), nullable=False, index=True)
    target_type = db.Column(db.String(64), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.full_name if self.user else 'System / Unknown',
            'action': self.action,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'details': self.details,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
