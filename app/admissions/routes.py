from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.admissions import admissions_bp
from app.extensions import db
from app.models import Enquiry, EnquiryStatus, Class, Batch, Student, User, Role
from app.utils.decorators import admin_required
from app.services.audit_service import log_action

@admissions_bp.route('/')
@login_required
@admin_required
def index():
    status = request.args.get('status', 'all')
    query = Enquiry.query

    if status != 'all':
        query = query.filter_by(status=status)

    enquiries = query.order_by(Enquiry.enquiry_date.desc()).all()
    classes = Class.query.order_by(Class.name).all()

    return render_template('admissions/index.html',
                           enquiries=enquiries,
                           classes=classes,
                           statuses=EnquiryStatus.CHOICES,
                           selected_status=status)

@admissions_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    classes = Class.query.order_by(Class.name).all()
    if request.method == 'POST':
        student_name = request.form.get('student_name', '').strip()
        parent_name = request.form.get('parent_name', '').strip()
        mobile = request.form.get('mobile', '').strip()
        email = request.form.get('email', '').strip()
        interested_class_id = request.form.get('interested_class_id', type=int)
        notes = request.form.get('notes', '').strip()

        enquiry = Enquiry(
            student_name=student_name,
            parent_name=parent_name,
            mobile=mobile,
            email=email,
            interested_class_id=interested_class_id,
            enquiry_date=datetime.utcnow().date(),
            status=EnquiryStatus.NEW,
            notes=notes
        )
        db.session.add(enquiry)
        db.session.commit()

        log_action('ENQUIRY_CREATED', target_type='Enquiry', target_id=enquiry.id, details=f"New admission enquiry for {student_name}")
        flash(f'Admission enquiry for "{student_name}" recorded.', 'success')
        return redirect(url_for('admissions.index'))

    return render_template('admissions/form.html', classes=classes)

@admissions_bp.route('/<int:enquiry_id>/status', methods=['POST'])
@login_required
@admin_required
def update_status(enquiry_id):
    enquiry = Enquiry.query.get_or_404(enquiry_id)
    new_status = request.form.get('status')
    notes = request.form.get('notes', '').strip()

    if new_status:
        enquiry.status = new_status
        if notes:
            enquiry.notes = (enquiry.notes or '') + f"\n[{datetime.utcnow().strftime('%Y-%m-%d')}]: {notes}"
        db.session.commit()
        flash(f'Enquiry status updated to "{new_status.replace("_", " ").title()}".', 'info')

    return redirect(url_for('admissions.index'))

@admissions_bp.route('/<int:enquiry_id>/convert', methods=['GET', 'POST'])
@login_required
@admin_required
def convert(enquiry_id):
    enquiry = Enquiry.query.get_or_404(enquiry_id)
    classes = Class.query.order_by(Class.name).all()
    batches = Batch.query.order_by(Batch.name).all()

    if request.method == 'POST':
        # Auto-fill student creation form from Enquiry data
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip() or f"{username}@eduflow.local"
        password = request.form.get('password', 'Student@123')
        class_id = request.form.get('class_id', type=int)
        batch_id = request.form.get('batch_id', type=int)

        if User.query.filter_by(username=username).first():
            flash('Username already exists. Choose another.', 'danger')
            return render_template('admissions/convert.html', enquiry=enquiry, classes=classes, batches=batches)

        # Split student_name into first and last name
        names = enquiry.student_name.split(' ', 1)
        first_name = names[0]
        last_name = names[1] if len(names) > 1 else 'Student'

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=Role.STUDENT,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        seq = Student.query.count() + 1
        student_code = f"STU-{datetime.utcnow().year}-{seq:04d}"

        student = Student(
            user_id=user.id,
            student_code=student_code,
            mobile=enquiry.mobile,
            parent_name=enquiry.parent_name,
            admission_date=datetime.utcnow().date(),
            class_id=class_id,
            batch_id=batch_id,
            status='active'
        )
        db.session.add(student)

        # Mark enquiry as converted
        enquiry.status = EnquiryStatus.CONVERTED
        db.session.commit()

        log_action('ENQUIRY_CONVERTED', target_type='Enquiry', target_id=enquiry.id, details=f"Converted enquiry into Student {student.full_name} ({student.student_code})")
        flash(f'Enquiry successfully converted! Student "{student.full_name}" registered with Code: {student.student_code}', 'success')
        return redirect(url_for('students.view', student_id=student.id))

    return render_template('admissions/convert.html', enquiry=enquiry, classes=classes, batches=batches)
