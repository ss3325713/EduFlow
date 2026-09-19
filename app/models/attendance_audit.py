from datetime import datetime
from app.extensions import db

class AttendanceAuditHistory(db.Model):
    __tablename__ = 'attendance_audit_history'

    id = db.Column(db.Integer, primary_key=True)
    attendance_type = db.Column(db.String(20), nullable=False, default='student')  # student, teacher
    record_id = db.Column(db.Integer, nullable=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=True, index=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), nullable=True, index=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='SET NULL'), nullable=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id', ondelete='SET NULL'), nullable=True)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True)
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    previous_status = db.Column(db.String(20), nullable=True)
    new_status = db.Column(db.String(20), nullable=False)
    changed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    changed_by_role = db.Column(db.String(20), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    student = db.relationship('Student')
    teacher = db.relationship('Teacher')
    academic_class = db.relationship('Class')
    batch = db.relationship('Batch')
    subject = db.relationship('Subject')
    changed_by_user = db.relationship('User', foreign_keys=[changed_by_user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'attendance_type': self.attendance_type,
            'record_id': self.record_id,
            'student_name': self.student.full_name if self.student else None,
            'teacher_name': self.teacher.full_name if self.teacher else None,
            'class_name': self.academic_class.name if self.academic_class else None,
            'batch_name': self.batch.name if self.batch else None,
            'subject_name': self.subject.name if self.subject else None,
            'attendance_date': self.attendance_date.isoformat() if self.attendance_date else None,
            'previous_status': self.previous_status or 'None',
            'new_status': self.new_status,
            'changed_by': self.changed_by_user.full_name if self.changed_by_user else 'System',
            'changed_by_role': self.changed_by_role or 'System',
            'reason': self.reason or '',
            'created_at': self.created_at.strftime('%Y-%m-%d %I:%M %p') if self.created_at else None
        }
