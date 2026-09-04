from datetime import datetime
from app.extensions import db

class EmailLog(db.Model):
    __tablename__ = 'email_logs'

    id = db.Column(db.Integer, primary_key=True)
    recipient_email = db.Column(db.String(120), nullable=False, index=True)
    sender_email = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(50), nullable=False, default='GENERAL', index=True)
    subject = db.Column(db.String(256), nullable=False)
    template_name = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='sent', index=True)  # queued, sent, failed
    failure_reason = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('email_logs', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'recipient_email': self.recipient_email,
            'sender_email': self.sender_email,
            'category': self.category,
            'subject': self.subject,
            'template_name': self.template_name,
            'status': self.status,
            'failure_reason': self.failure_reason,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<EmailLog {self.category} -> {self.recipient_email} [{self.status}]>'
