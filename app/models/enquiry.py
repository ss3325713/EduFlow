from datetime import datetime
from app.extensions import db

class EnquiryStatus:
    NEW = 'new'
    CONTACTED = 'contacted'
    INTERESTED = 'interested'
    FOLLOW_UP = 'follow_up'
    CONVERTED = 'converted'
    CLOSED = 'closed'

    CHOICES = [
        (NEW, 'New Enquiry'),
        (CONTACTED, 'Contacted'),
        (INTERESTED, 'Interested'),
        (FOLLOW_UP, 'Follow-up Required'),
        (CONVERTED, 'Converted to Admission'),
        (CLOSED, 'Closed / Not Interested')
    ]

class Enquiry(db.Model):
    __tablename__ = 'enquiries'

    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(128), nullable=False)
    parent_name = db.Column(db.String(128), nullable=True)
    mobile = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(128), nullable=True)
    interested_class_id = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='SET NULL'), nullable=True)
    enquiry_date = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    follow_up_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default=EnquiryStatus.NEW, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    interested_class = db.relationship('Class')

    def to_dict(self):
        return {
            'id': self.id,
            'student_name': self.student_name,
            'parent_name': self.parent_name,
            'mobile': self.mobile,
            'email': self.email,
            'interested_class_id': self.interested_class_id,
            'interested_class_name': self.interested_class.name if self.interested_class else 'Unspecified',
            'enquiry_date': self.enquiry_date.isoformat() if self.enquiry_date else None,
            'follow_up_date': self.follow_up_date.isoformat() if self.follow_up_date else None,
            'status': self.status,
            'notes': self.notes
        }
