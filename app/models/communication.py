from datetime import datetime
from app.extensions import db

class Announcement(db.Model):
    __tablename__ = 'announcements'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(128), nullable=False)
    content = db.Column(db.Text, nullable=False)
    target_role = db.Column(db.String(20), default='all')  # all, teacher, student, parent
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='CASCADE'), nullable=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('batches.id', ondelete='CASCADE'), nullable=True)
    priority = db.Column(db.String(20), default='normal')  # normal, high, urgent
    publish_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.Date, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    created_by_user = db.relationship('User')
    academic_class = db.relationship('Class')
    batch = db.relationship('Batch')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'target_role': self.target_role,
            'class_id': self.class_id,
            'class_name': self.academic_class.name if self.academic_class else 'All Classes',
            'batch_id': self.batch_id,
            'batch_name': self.batch.name if self.batch else 'All Batches',
            'priority': self.priority,
            'publish_date': self.publish_date.isoformat() if self.publish_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'created_by': self.created_by_user.full_name if self.created_by_user else 'Admin'
        }

class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    title = db.Column(db.String(128), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(256), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()

    def mark_as_deleted(self):
        if not self.is_deleted:
            self.is_deleted = True
            self.deleted_at = datetime.utcnow()

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'link': self.link,
            'is_read': self.is_read,
            'read_at': self.read_at.isoformat() if self.read_at else None,
            'is_deleted': self.is_deleted,
            'deleted_at': self.deleted_at.isoformat() if self.deleted_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class TeacherRequest(db.Model):
    __tablename__ = 'teacher_requests'

    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('teachers.id', ondelete='CASCADE'), nullable=False, index=True)
    request_type = db.Column(db.String(50), nullable=False, default='other')  # leave, schedule_change, batch_allocation, new_class, other
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)  # pending, under_review, approved, rejected, completed
    admin_response = db.Column(db.Text, nullable=True)

    # Category Specific Fields
    # Leave Request
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)

    # Schedule Change Request
    timetable_id = db.Column(db.Integer, db.ForeignKey('timetables.id', ondelete='SET NULL'), nullable=True)
    change_action = db.Column(db.String(20), nullable=True)  # change_time, postpone, cancel

    # Allocation & New Class Request
    target_class_id = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='SET NULL'), nullable=True)
    target_batch_id = db.Column(db.Integer, db.ForeignKey('batches.id', ondelete='SET NULL'), nullable=True)
    target_subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id', ondelete='SET NULL'), nullable=True)
    allocation_action = db.Column(db.String(20), nullable=True)  # assign, remove

    # Proposed timing (Schedule Change or New Class)
    proposed_date = db.Column(db.Date, nullable=True)
    proposed_time = db.Column(db.Time, nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=True, default=60)
    attachment_path = db.Column(db.String(256), nullable=True)

    # Processing metadata
    processed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    teacher = db.relationship('Teacher', backref=db.backref('requests', lazy='dynamic', cascade='all, delete-orphan'))
    timetable = db.relationship('Timetable')
    target_class = db.relationship('Class')
    target_batch = db.relationship('Batch')
    target_subject = db.relationship('Subject')
    processed_by_user = db.relationship('User', foreign_keys=[processed_by_user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'teacher_id': self.teacher_id,
            'teacher_name': self.teacher.full_name if self.teacher and self.teacher.user else 'Teacher',
            'teacher_code': self.teacher.teacher_code if self.teacher else '',
            'request_type': self.request_type,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'admin_response': self.admin_response,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'timetable_id': self.timetable_id,
            'change_action': self.change_action,
            'target_class_name': self.target_class.name if self.target_class else None,
            'target_batch_name': self.target_batch.name if self.target_batch else None,
            'target_subject_name': self.target_subject.name if self.target_subject else None,
            'proposed_date': self.proposed_date.isoformat() if self.proposed_date else None,
            'proposed_time': self.proposed_time.strftime('%H:%M') if self.proposed_time else None,
            'duration_minutes': self.duration_minutes,
            'attachment_path': self.attachment_path,
            'processed_by': self.processed_by_user.full_name if self.processed_by_user else None,
            'processed_at': self.processed_at.strftime('%Y-%m-%d %H:%M') if self.processed_at else None,
            'created_at': self.created_at.strftime('%Y-%m-%d %I:%M %p') if self.created_at else None,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %I:%M %p') if self.updated_at else None
        }


