from datetime import datetime
import random
import string
from app.extensions import db
from app.models.fee import StudentFee, FeePayment
from app.services.audit_service import log_action

class FeeService:

    @staticmethod
    def generate_receipt_number():
        date_str = datetime.utcnow().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        return f"REC-{date_str}-{random_str}"

    @staticmethod
    def record_payment(student_fee_id, amount_paid, payment_method='cash', notes=None, recorded_by_user_id=None):
        student_fee = StudentFee.query.get(student_fee_id)
        if not student_fee:
            raise ValueError("Student fee record not found.")

        if amount_paid <= 0:
            raise ValueError("Payment amount must be greater than zero.")

        receipt_number = FeeService.generate_receipt_number()

        payment = FeePayment(
            student_fee_id=student_fee.id,
            receipt_number=receipt_number,
            amount_paid=amount_paid,
            payment_method=payment_method,
            payment_date=datetime.utcnow(),
            transaction_notes=notes,
            recorded_by_user_id=recorded_by_user_id,
            status='valid'
        )

        student_fee.total_paid += amount_paid
        student_fee.update_status()

        db.session.add(payment)
        db.session.commit()

        log_action(
            action='FEE_PAYMENT_RECORDED',
            target_type='FeePayment',
            target_id=payment.id,
            details=f"Recorded payment of {amount_paid} ({payment_method}) for Student ID {student_fee.student_id}. Receipt: {receipt_number}",
            user_id=recorded_by_user_id
        )

        return payment

    @staticmethod
    def reverse_payment(payment_id, reason="Admin Reversal", user_id=None):
        payment = FeePayment.query.get(payment_id)
        if not payment:
            raise ValueError("Payment record not found.")

        if payment.status == 'cancelled':
            raise ValueError("Payment has already been cancelled.")

        payment.status = 'cancelled'
        student_fee = payment.student_fee
        if student_fee:
            student_fee.total_paid = max(0.0, student_fee.total_paid - payment.amount_paid)
            student_fee.update_status()

        db.session.commit()

        log_action(
            action='FEE_PAYMENT_CANCELLED',
            target_type='FeePayment',
            target_id=payment.id,
            details=f"Cancelled receipt {payment.receipt_number} of amount {payment.amount_paid}. Reason: {reason}",
            user_id=user_id
        )

        return payment
