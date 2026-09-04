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

        # ----------------------------------------------------
        # Email Notification Integration for Fee Receipts
        # ----------------------------------------------------
        try:
            from app.models import Student, InstituteSettings, EmailCategory
            from app.services.email_service import EmailService

            student = student_fee.student
            institute = InstituteSettings.get_settings()
            institute_name = institute.name if institute else 'EduFlow Academy'

            context = {
                'student_name': student.full_name if student else 'Student',
                'parent_name': 'Parent / Guardian',
                'institute_name': institute_name,
                'receipt_number': receipt_number,
                'amount_paid': amount_paid,
                'payment_date': datetime.utcnow().strftime('%B %d, %Y'),
                'payment_method': payment_method,
                'remaining_balance': student_fee.balance
            }

            recipients = set()
            if student and student.user and student.user.email:
                recipients.add((student.user.email, student.user.id))

            if student:
                for link in student.parent_links:
                    if link.parent and link.parent.user and link.parent.user.email:
                        recipients.add((link.parent.user.email, link.parent.user.id))

            for email_addr, u_id in recipients:
                EmailService.send_email(
                    to_email=email_addr,
                    subject=f"Fee Payment Confirmation — Receipt #{receipt_number}",
                    template_name='fee_receipt_email',
                    context=context,
                    category=EmailCategory.FINANCIAL,
                    user_id=u_id
                )
        except Exception as err:
            pass

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
