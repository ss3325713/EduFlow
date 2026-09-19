from datetime import datetime
from app.extensions import db

class TeacherAttendance(db.Model):
    __tablename__ = 'teacher_attendance'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date, index=True)
    status = db.Column(db.String(20), nullable=False, default='present')  # present, absent, leave
    marked_time = db.Column(db.DateTime, nullable=True)
    is_auto_marked = db.Column(db.Boolean, default=False, nullable=False)
    admin_corrected = db.Column(db.Boolean, default=False, nullable=False)
    correction_reason = db.Column(db.Text, nullable=True)
    remarks = db.Column(db.Text, nullable=True)
    corrected_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('teacher_id', 'date', name='_teacher_date_uc'),
    )

    teacher = db.relationship('Teacher', backref=db.backref('attendance_records', lazy='dynamic', cascade='all, delete-orphan'))
    corrected_by_user = db.relationship('User', foreign_keys=[corrected_by_user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.full_name if self.teacher else 'Unknown',
            'teacher_code': self.teacher.teacher_code if self.teacher else '',
            'date': self.date.isoformat() if self.date else None,
            'status': self.status,
            'marked_time': self.marked_time.strftime('%I:%M %p') if self.marked_time else None,
            'is_auto_marked': self.is_auto_marked,
            'admin_corrected': self.admin_corrected,
            'correction_reason': self.correction_reason,
            'corrected_by': self.corrected_by_user.full_name if self.corrected_by_user else None
        }
