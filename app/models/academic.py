from datetime import datetime
from app.extensions import db

class Class(db.Model):
    __tablename__ = 'classes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    subjects = db.relationship('Subject', backref='academic_class', lazy='dynamic', cascade='all, delete-orphan')
    batches = db.relationship('Batch', backref='academic_class', lazy='dynamic', cascade='all, delete-orphan')
    students = db.relationship('Student', backref='academic_class', lazy='dynamic')
    fee_structures = db.relationship('FeeStructure', backref='academic_class', lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'description': self.description,
            'subject_count': self.subjects.count(),
            'batch_count': self.batches.count(),
            'student_count': self.students.count()
        }

    def __repr__(self):
        return f'<Class {self.name}>'

class Subject(db.Model):
    __tablename__ = 'subjects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('name', 'class_id', name='_subject_class_uc'),)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'class_id': self.class_id,
            'class_name': self.academic_class.name if self.academic_class else None,
            'description': self.description
        }

    def __repr__(self):
        return f'<Subject {self.name} ({self.code})>'

class Batch(db.Model):
    __tablename__ = 'batches'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    code = db.Column(db.String(20), nullable=False, unique=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    max_capacity = db.Column(db.Integer, default=30, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    schedule_description = db.Column(db.String(256), nullable=True)
    status = db.Column(db.String(20), default='active')  # active, completed, archived
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    students = db.relationship('Student', backref='batch', lazy='dynamic')
    teacher_assignments = db.relationship('TeacherAssignment', backref='batch', lazy='dynamic', cascade='all, delete-orphan')
    attendance_records = db.relationship('Attendance', backref='batch', lazy='dynamic', cascade='all, delete-orphan')
    timetables = db.relationship('Timetable', backref='batch', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def current_student_count(self):
        return self.students.count()

    @property
    def is_full(self):
        return self.current_student_count >= self.max_capacity

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'class_id': self.class_id,
            'class_name': self.academic_class.name if self.academic_class else None,
            'max_capacity': self.max_capacity,
            'current_student_count': self.current_student_count,
            'is_full': self.is_full,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'schedule_description': self.schedule_description,
            'status': self.status
        }

    def __repr__(self):
        return f'<Batch {self.name}>'

class TeacherAssignment(db.Model):
    __tablename__ = 'teacher_assignments'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id', ondelete='CASCADE'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint preventing duplicate teacher-batch-subject mapping
    __table_args__ = (
        db.UniqueConstraint('teacher_id', 'batch_id', 'subject_id', name='_teacher_batch_subject_uc'),
    )

    academic_class = db.relationship('Class')
    subject = db.relationship('Subject')

    def to_dict(self):
        return {
            'id': self.id,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.full_name if self.teacher else None,
            'class_id': self.class_id,
            'class_name': self.academic_class.name if self.academic_class else None,
            'batch_id': self.batch_id,
            'batch_name': self.batch.name if self.batch else None,
            'subject_id': self.subject_id,
            'subject_name': self.subject.name if self.subject else None
        }
