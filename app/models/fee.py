from datetime import datetime
from app.extensions import db

class FeeStructure(db.Model):
    __tablename__ = 'fee_structures'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id', ondelete='CASCADE'), nullable=False)
    admission_fee = db.Column(db.Float, default=0.0)
    course_fee = db.Column(db.Float, default=0.0)
    monthly_fee = db.Column(db.Float, default=0.0)
    exam_fee = db.Column(db.Float, default=0.0)
    other_charges = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student_fees = db.relationship('StudentFee', backref='fee_structure', lazy='dynamic')

    @property
    def total_calculated_amount(self):
        return (self.admission_fee + self.course_fee + (self.monthly_fee * 12) +
                self.exam_fee + self.other_charges - self.discount_amount)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'class_id': self.class_id,
            'class_name': self.academic_class.name if self.academic_class else None,
            'admission_fee': self.admission_fee,
            'course_fee': self.course_fee,
            'monthly_fee': self.monthly_fee,
            'exam_fee': self.exam_fee,
            'other_charges': self.other_charges,
            'discount_amount': self.discount_amount,
            'total_amount': self.total_calculated_amount
        }

class StudentFee(db.Model):
    __tablename__ = 'student_fees'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id', ondelete='CASCADE'), nullable=False)
    fee_structure_id = db.Column(db.Integer, db.ForeignKey('fee_structures.id', ondelete='SET NULL'), nullable=True)
    total_payable = db.Column(db.Float, nullable=False, default=0.0)
    total_paid = db.Column(db.Float, nullable=False, default=0.0)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, partial, paid, overdue
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    payments = db.relationship('FeePayment', backref='student_fee', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def balance(self):
        return max(0.0, round(self.total_payable - self.total_paid, 2))

    def update_status(self):
        if self.balance <= 0 and self.total_payable > 0:
            self.status = 'paid'
        elif self.total_paid > 0:
            self.status = 'partial'
        elif self.due_date and self.due_date < datetime.utcnow().date():
            self.status = 'overdue'
        else:
            self.status = 'pending'

    def to_dict(self):
        self.update_status()
        return {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student.full_name if self.student else None,
            'student_code': self.student.student_code if self.student else None,
            'fee_structure_name': self.fee_structure.name if self.fee_structure else 'Custom Plan',
            'total_payable': self.total_payable,
            'total_paid': self.total_paid,
            'balance': self.balance,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'status': self.status
        }

class FeePayment(db.Model):
    __tablename__ = 'fee_payments'

    id = db.Column(db.Integer, primary_key=True)
    student_fee_id = db.Column(db.Integer, db.ForeignKey('student_fees.id', ondelete='CASCADE'), nullable=False)
    receipt_number = db.Column(db.String(32), unique=True, nullable=False, index=True)
    amount_paid = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(32), default='cash')  # cash, bank_transfer, upi, cheque, other
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    transaction_notes = db.Column(db.Text, nullable=True)
    recorded_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(db.String(20), default='valid')  # valid, cancelled

    recorded_by_user = db.relationship('User', foreign_keys=[recorded_by_user_id])

    def to_dict(self):
        return {
            'id': self.id,
            'student_fee_id': self.student_fee_id,
            'student_name': self.student_fee.student.full_name if (self.student_fee and self.student_fee.student) else None,
            'receipt_number': self.receipt_number,
            'amount_paid': self.amount_paid,
            'payment_method': self.payment_method,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None,
            'transaction_notes': self.transaction_notes,
            'recorded_by': self.recorded_by_user.full_name if self.recorded_by_user else 'Admin',
            'status': self.status
        }
