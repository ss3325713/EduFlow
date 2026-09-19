from datetime import datetime
from app.extensions import db

class DiaryEntry(db.Model):
    __tablename__ = 'diary_entries'

    id = db.Column(db.Integer, primary_key=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    diary_date = db.Column(db.Date, nullable=False, index=True)
    encrypted_content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    owner = db.relationship('User', backref=db.backref('diary_entries', lazy='dynamic', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('owner_user_id', 'diary_date', name='_owner_diary_date_uc'),
        db.Index('idx_owner_diary_date', 'owner_user_id', 'diary_date'),
    )

    def to_dict(self, decrypted_text=None):
        return {
            'id': self.id,
            'owner_user_id': self.owner_user_id,
            'diary_date': self.diary_date.isoformat(),
            'content': decrypted_text if decrypted_text is not None else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
