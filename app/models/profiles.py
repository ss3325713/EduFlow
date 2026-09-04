from datetime import datetime
from app.extensions import db

class Teacher(db.Model):
    __tablename__ = 'teachers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    teacher_code = db.Column(db.String(20), unique=True, nullable=False)
    mobile = db.Column(db.String(20), nullable=True)
    qualification = db.Column(db.String(128), nullable=True)
    specialization = db.Column(db.String(128), nullable=True)
    joining_date = db.Column(db.Date, nullable=True)
    employment_status = db.Column(db.String(20), default='active')  # active, on_leave, resigned

    assignments = db.relationship('TeacherAssignment', backref='teacher', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def full_name(self):
        return self.user.full_name if self.user else "Unknown Teacher"

    @property
    def email(self):
        return self.user.email if self.user else ""

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'teacher_code': self.teacher_code,
            'full_name': self.full_name,
            'email': self.email,
            'mobile': self.mobile,
            'qualification': self.qualification,
            'specialization': self.specialization,
            'joining_date': self.joining_date.isoformat() if self.joining_date else None,
            'employment_status': self.employment_status,
            'assigned_batches_count': len(set(a.batch_id for a in self.assignments))
        }

    def __repr__(self):
        return f'<Teacher {self.teacher_code} - {self.full_name}>'

class Student(db.Model):
    __tablename__ = 'students'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    student_code = db.Column(db.String(20), unique=True, nullable=False)
    dob = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(10), nullable=True)
    mobile = db.Column(db.String(20), nullable=True)
    address = db.Column(db.Text, nullable=True)
    parent_name = db.Column(db.String(128), nullable=True)
    parent_mobile = db.Column(db.String(20), nullable=True)
    admission_date = db.Column(db.Date, default=datetime.utcnow)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='SET NULL'), nullable=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id', ondelete='SET NULL'), nullable=True)
    roll_number = db.Column(db.String(20), nullable=True)
    status = db.Column(db.String(20), default='active')  # active, inactive, archived

    # Relationships
    parent_links = db.relationship('StudentParent', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    attendance_records = db.relationship('Attendance', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    fees = db.relationship('StudentFee', backref='student', lazy='dynamic', cascade='all, delete-orphan')
    marks = db.relationship('Mark', backref='student', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def full_name(self):
        return self.user.full_name if self.user else "Unknown Student"

    @property
    def email(self):
        return self.user.email if self.user else ""

    @property
    def attendance_percentage(self):
        total = self.attendance_records.count()
        if total == 0:
            return 100.0
        present = self.attendance_records.filter_by(status='present').count()
        late = self.attendance_records.filter_by(status='late').count()
        return round(((present + late) / total) * 100, 1)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'student_code': self.student_code,
            'full_name': self.full_name,
            'email': self.email,
            'dob': self.dob.isoformat() if self.dob else None,
            'gender': self.gender,
            'mobile': self.mobile,
            'address': self.address,
            'parent_name': self.parent_name,
            'parent_mobile': self.parent_mobile,
            'admission_date': self.admission_date.isoformat() if self.admission_date else None,
            'class_id': self.class_id,
            'class_name': self.academic_class.name if self.academic_class else 'Unassigned',
            'batch_id': self.batch_id,
            'batch_name': self.batch.name if self.batch else 'Unassigned',
            'roll_number': self.roll_number,
            'status': self.status,
            'attendance_percentage': self.attendance_percentage
        }

    def __repr__(self):
        return f'<Student {self.student_code} - {self.full_name}>'

class Parent(db.Model):
    __tablename__ = 'parents'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    mobile = db.Column(db.String(20), nullable=True)
    occupation = db.Column(db.String(64), nullable=True)
    address = db.Column(db.Text, nullable=True)

    student_links = db.relationship('StudentParent', backref='parent', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def full_name(self):
        return self.user.full_name if self.user else "Unknown Parent"

    @property
    def email(self):
        return self.user.email if self.user else ""

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'full_name': self.full_name,
            'email': self.email,
            'mobile': self.mobile,
            'occupation': self.occupation,
            'linked_children_count': self.student_links.count()
        }

class StudentParent(db.Model):
    __tablename__ = 'student_parents'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('parents.id', ondelete='CASCADE'), nullable=False)
    relationship = db.Column(db.String(20), default='parent')  # father, mother, guardian

    __table_args__ = (
        db.UniqueConstraint('student_id', 'parent_id', name='_student_parent_uc'),
    )

class StudentRequest(db.Model):
    __tablename__ = 'student_requests'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    requested_by_teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False)
    request_type = db.Column(db.String(20), nullable=False)  # deletion, suspension
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship('Student', backref=db.backref('requests', lazy='dynamic', cascade='all, delete-orphan'))
    requested_by_teacher = db.relationship('Teacher', backref='student_requests')
    processed_by_user = db.relationship('User', foreign_keys=[processed_by_user_id])
