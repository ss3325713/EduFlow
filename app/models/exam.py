from datetime import datetime
from app.extensions import db

class Exam(db.Model):
    __tablename__ = 'exams'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    exam_type = db.Column(db.String(32), default='unit_test')  # unit_test, midterm, final, mock
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id', ondelete='CASCADE'), nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
    max_marks = db.Column(db.Float, default=100.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    academic_class = db.relationship('Class')
    batch = db.relationship('Batch')
    marks = db.relationship('Mark', backref='exam', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'exam_type': self.exam_type,
            'class_id': self.class_id,
            'class_name': self.academic_class.name if self.academic_class else None,
            'batch_id': self.batch_id,
            'batch_name': self.batch.name if self.batch else None,
            'exam_date': self.exam_date.isoformat() if self.exam_date else None,
            'max_marks': self.max_marks
        }

class Mark(db.Model):
    __tablename__ = 'marks'

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('exams.id', ondelete='CASCADE'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    marks_obtained = db.Column(db.Float, nullable=False, default=0.0)
    max_marks = db.Column(db.Float, nullable=False, default=100.0)
    grade = db.Column(db.String(5), nullable=True)
    remarks = db.Column(db.String(256), nullable=True)
    entered_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('exam_id', 'subject_id', 'student_id', name='_exam_subject_student_uc'),
    )

    subject = db.relationship('Subject')
    entered_by_user = db.relationship('User')

    @property
    def percentage(self):
        if self.max_marks <= 0:
            return 0.0
        return round((self.marks_obtained / self.max_marks) * 100, 1)

    def calculate_grade(self):
        pct = self.percentage
        if pct >= 90: self.grade = 'A+'
        elif pct >= 80: self.grade = 'A'
        elif pct >= 70: self.grade = 'B'
        elif pct >= 60: self.grade = 'C'
        elif pct >= 50: self.grade = 'D'
        else: self.grade = 'F'
        return self.grade

    def to_dict(self):
        self.calculate_grade()
        return {
            'id': self.id,
            'exam_id': self.exam_id,
            'exam_title': self.exam.title if self.exam else None,
            'subject_id': self.subject_id,
            'subject_name': self.subject.name if self.subject else None,
            'student_id': self.student_id,
            'student_name': self.student.full_name if self.student else None,
            'marks_obtained': self.marks_obtained,
            'max_marks': self.max_marks,
            'percentage': self.percentage,
            'grade': self.grade,
            'remarks': self.remarks
        }
