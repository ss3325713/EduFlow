from datetime import datetime
from app.extensions import db

class AttendanceStatus:
    PRESENT = 'present'
    ABSENT = 'absent'
    LATE = 'late'
    EXCUSED = 'excused'

    CHOICES = [
        (PRESENT, 'Present'),
        (ABSENT, 'Absent'),
        (LATE, 'Late'),
        (EXCUSED, 'Excused')
    ]

class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id', ondelete='CASCADE'), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow().date, index=True)
    status = db.Column(db.String(20), nullable=False, default=AttendanceStatus.PRESENT)
    marked_by_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='SET NULL'), nullable=True)
    remarks = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('student_id', 'batch_id', 'date', name='_student_batch_date_uc'),
    )

    marked_by_teacher = db.relationship('Teacher')

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.full_name if self.student else None,
            'student_code': self.student.student_code if self.student else None,
            'batch_id': self.batch_id,
            'batch_name': self.batch.name if self.batch else None,
            'date': self.date.isoformat(),
            'status': self.status,
            'marked_by': self.marked_by_teacher.full_name if self.marked_by_teacher else 'Admin',
            'remarks': self.remarks
        }
