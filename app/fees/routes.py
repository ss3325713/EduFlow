from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from app.fees import fees_bp
from app.extensions import db
from app.models import FeeStructure, StudentFee, FeePayment, Student, Class
from app.utils.decorators import admin_required
from app.services.fee_service import FeeService

@fees_bp.route('/')
@login_required
def index():
    # Teachers do not have access to fee management or collection
    if current_user.is_teacher():
        flash('Teachers do not have access to fee and receipt management.', 'danger')
        return redirect(url_for('dashboard.index'))

    # Role-based access: Student/Parent sees their fee record; Admin sees full collection dashboard
    if current_user.is_student():
        student = current_user.student_profile
        fee_record = StudentFee.query.filter_by(student_id=student.id).first() if student else None
        payments = fee_record.payments.order_by(FeePayment.payment_date.desc()).all() if fee_record else []
        return render_template('fees/student_view.html', fee_record=fee_record, payments=payments)

    if current_user.is_parent():
        parent = current_user.parent_profile
        linked_students = [link.student for link in parent.student_links.all()] if parent else []
        student_fees = StudentFee.query.filter(StudentFee.student_id.in_([s.id for s in linked_students])).all() if linked_students else []
        return render_template('fees/parent_view.html', student_fees=student_fees)

    # Admin Collection Dashboard
    search = request.args.get('search', '').strip()
    status = request.args.get('status', 'all')
    class_id = request.args.get('class_id', type=int)

    query = StudentFee.query.join(Student)

    if status != 'all':
        query = query.filter(StudentFee.status == status)

    if class_id:
        query = query.filter(Student.class_id == class_id)

    if search:
        query = query.filter(Student.student_code.ilike(f'%{search}%'))

    student_fees = query.all()
    classes = Class.query.order_by(Class.name).all()

    # Collection summary
    today = datetime.utcnow().date()
    first_day_month = today.replace(day=1)

    today_collection = db.session.query(
        func.coalesce(func.sum(FeePayment.amount_paid), 0.0)
    ).filter(
        func.date(FeePayment.payment_date) == today,
        FeePayment.status == 'valid'
    ).scalar()

    monthly_collection = db.session.query(
        func.coalesce(func.sum(FeePayment.amount_paid), 0.0)
    ).filter(
        FeePayment.payment_date >= first_day_month,
        FeePayment.status == 'valid'
    ).scalar()

    total_pending = db.session.query(
        func.coalesce(func.sum(StudentFee.total_payable - StudentFee.total_paid), 0.0)
    ).scalar()

    recent_payments = FeePayment.query.order_by(FeePayment.payment_date.desc()).limit(10).all()

    return render_template('fees/dashboard.html',
                           student_fees=student_fees,
                           classes=classes,
                           today_collection=today_collection,
                           monthly_collection=monthly_collection,
                           total_pending=total_pending,
                           recent_payments=recent_payments,
                           selected_status=status,
                           selected_class=class_id,
                           search=search)

@fees_bp.route('/structures', methods=['GET', 'POST'])
@login_required
@admin_required
def structures():
    structures = FeeStructure.query.all()
    classes = Class.query.order_by(Class.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        class_id = request.form.get('class_id', type=int)
        admission_fee = request.form.get('admission_fee', type=float, default=0.0)
        course_fee = request.form.get('course_fee', type=float, default=0.0)
        monthly_fee = request.form.get('monthly_fee', type=float, default=0.0)
        exam_fee = request.form.get('exam_fee', type=float, default=0.0)
        other_charges = request.form.get('other_charges', type=float, default=0.0)
        discount_amount = request.form.get('discount_amount', type=float, default=0.0)

        fs = FeeStructure(
            name=name,
            class_id=class_id,
            admission_fee=admission_fee,
            course_fee=course_fee,
            monthly_fee=monthly_fee,
            exam_fee=exam_fee,
            other_charges=other_charges,
            discount_amount=discount_amount
        )
        db.session.add(fs)
        db.session.commit()

        flash(f'Fee Structure "{fs.name}" created successfully.', 'success')
        return redirect(url_for('fees.structures'))

    return render_template('fees/structures.html', structures=structures, classes=classes)

@fees_bp.route('/collect/<int:student_fee_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def collect(student_fee_id):
    student_fee = StudentFee.query.get_or_404(student_fee_id)

    if request.method == 'POST':
        amount_paid = request.form.get('amount_paid', type=float)
        payment_method = request.form.get('payment_method', 'cash')
        notes = request.form.get('transaction_notes', '').strip()

        try:
            payment = FeeService.record_payment(
                student_fee_id=student_fee.id,
                amount_paid=amount_paid,
                payment_method=payment_method,
                notes=notes,
                recorded_by_user_id=current_user.id
            )
            flash(f'Payment of ${amount_paid:.2f} recorded successfully! Receipt #{payment.receipt_number}', 'success')
            return redirect(url_for('fees.receipt', payment_id=payment.id))
        except ValueError as e:
            flash(str(e), 'danger')

    return render_template('fees/collect.html', student_fee=student_fee)

@fees_bp.route('/receipt/<int:payment_id>')
@login_required
def receipt(payment_id):
    payment = FeePayment.query.get_or_404(payment_id)
    student = payment.student_fee.student

    if current_user.is_teacher():
        flash('Teachers do not have access to fee receipts.', 'danger')
        return redirect(url_for('dashboard.index'))

    # Permission check
    if current_user.is_student() and (not current_user.student_profile or current_user.student_profile.id != student.id):
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard.index'))

    return render_template('fees/receipt.html', payment=payment, student=student)

@fees_bp.route('/payment/<int:payment_id>/reverse', methods=['POST'])
@login_required
@admin_required
def reverse(payment_id):
    reason = request.form.get('reason', 'Admin Cancellation')
    try:
        payment = FeeService.reverse_payment(payment_id=payment_id, reason=reason, user_id=current_user.id)
        flash(f'Receipt #{payment.receipt_number} has been reversed/cancelled.', 'warning')
    except ValueError as e:
        flash(str(e), 'danger')

    return redirect(url_for('fees.index'))
