from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.students import students_bp
from app.extensions import db
from app.models import (
    Student, User, Role, Class, Batch, FeeStructure, StudentFee,
    Attendance, Mark, Homework, StudyMaterial, Parent, StudentParent, StudentRequest
)
from app.utils.decorators import admin_required, teacher_required, super_admin_required
from app.services.audit_service import log_action

@students_bp.route('/')
@login_required
@teacher_required
def index():
    search = request.args.get('search', '').strip()
    class_id = request.args.get('class_id', type=int)
    batch_id = request.args.get('batch_id', type=int)
    status = request.args.get('status', 'all')

    query = Student.query.join(User)

    if status != 'all':
        query = query.filter(Student.status == status)

    if search:
        query = query.filter(
            (User.first_name.ilike(f'%{search}%')) |
            (User.last_name.ilike(f'%{search}%')) |
            (Student.student_code.ilike(f'%{search}%')) |
            (Student.mobile.ilike(f'%{search}%'))
        )

    if class_id:
        query = query.filter(Student.class_id == class_id)

    if batch_id:
        query = query.filter(Student.batch_id == batch_id)

    students = query.order_by(User.first_name.asc()).all()
    classes = Class.query.order_by(Class.name).all()
    batches = Batch.query.order_by(Batch.name).all()
    pending_requests_count = StudentRequest.query.filter_by(status='pending').count() if current_user.is_admin() else 0

    return render_template('students/index.html',
                           students=students,
                           classes=classes,
                           batches=batches,
                           search=search,
                           selected_class=class_id,
                           selected_batch=batch_id,
                           selected_status=status,
                           pending_requests_count=pending_requests_count)

@students_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    classes = Class.query.order_by(Class.name).all()
    batches = Batch.query.order_by(Batch.name).all()
    fee_structures = FeeStructure.query.all()

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', 'Student@123')
        dob_str = request.form.get('dob')
        gender = request.form.get('gender')
        mobile = request.form.get('mobile', '').strip()
        address = request.form.get('address', '').strip()
        parent_name = request.form.get('parent_name', '').strip()
        parent_mobile = request.form.get('parent_mobile', '').strip()
        class_id = request.form.get('class_id', type=int)
        batch_id = request.form.get('batch_id', type=int)
        roll_number = request.form.get('roll_number', '').strip()
        fee_structure_id = request.form.get('fee_structure_id', type=int)

        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose a different username.', 'danger')
            return render_template('students/form.html', classes=classes, batches=batches, fee_structures=fee_structures)

        if User.query.filter_by(email=email).first():
            flash('Email already exists. Please enter a unique email.', 'danger')
            return render_template('students/form.html', classes=classes, batches=batches, fee_structures=fee_structures)

        if batch_id:
            batch = Batch.query.get(batch_id)
            if batch and batch.is_full:
                override = request.form.get('override_capacity')
                if not override:
                    flash(f'Batch "{batch.name}" has reached maximum capacity ({batch.max_capacity}). Select override to proceed.', 'warning')
                    return render_template('students/form.html', classes=classes, batches=batches, fee_structures=fee_structures, show_override=True)

        code_seq = Student.query.count() + 1
        student_code = f"STU-{datetime.utcnow().year}-{code_seq:04d}"

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

        dob = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None

        student = Student(
            user_id=user.id,
            student_code=student_code,
            dob=dob,
            gender=gender,
            mobile=mobile,
            address=address,
            parent_name=parent_name,
            parent_mobile=parent_mobile,
            admission_date=datetime.utcnow().date(),
            class_id=class_id,
            batch_id=batch_id,
            roll_number=roll_number,
            status='active'
        )
        db.session.add(student)
        db.session.flush()

        if fee_structure_id:
            fs = FeeStructure.query.get(fee_structure_id)
            if fs:
                student_fee = StudentFee(
                    student_id=student.id,
                    fee_structure_id=fs.id,
                    total_payable=fs.total_calculated_amount,
                    total_paid=0.0,
                    status='pending'
                )
                db.session.add(student_fee)

        db.session.commit()
        log_action('STUDENT_CREATED', target_type='Student', target_id=student.id, details=f"Created student {student.full_name} ({student.student_code})")
        flash(f'Student "{student.full_name}" registered successfully with Code: {student.student_code}', 'success')
        return redirect(url_for('students.view', student_id=student.id))

    return render_template('students/form.html', classes=classes, batches=batches, fee_structures=fee_structures)

@students_bp.route('/<int:student_id>')
@login_required
def view(student_id):
    student = Student.query.get_or_404(student_id)

    if current_user.is_student() and (not current_user.student_profile or current_user.student_profile.id != student.id):
        flash('You can only view your own profile.', 'danger')
        return redirect(url_for('dashboard.index'))

    if current_user.is_parent():
        parent_profile = current_user.parent_profile
        linked_ids = [link.student_id for link in parent_profile.student_links.all()] if parent_profile else []
        if student.id not in linked_ids:
            flash("You can only view your linked children's profiles.", 'danger')
            return redirect(url_for('dashboard.index'))

    active_tab = request.args.get('tab', 'overview')
    attendance_records = Attendance.query.filter_by(student_id=student.id).order_by(Attendance.date.desc()).limit(30).all()
    fee_record = StudentFee.query.filter_by(student_id=student.id).first()
    marks = Mark.query.filter_by(student_id=student.id).all()
    homework_list = Homework.query.filter_by(batch_id=student.batch_id).order_by(Homework.due_date.desc()).all() if student.batch_id else []
    study_materials = StudyMaterial.query.filter_by(batch_id=student.batch_id).order_by(StudyMaterial.upload_date.desc()).all() if student.batch_id else []
    all_batches = Batch.query.filter_by(status='active').all()

    return render_template('students/view.html',
                           student=student,
                           active_tab=active_tab,
                           attendance_records=attendance_records,
                           fee_record=fee_record,
                           marks=marks,
                           homework_list=homework_list,
                           study_materials=study_materials,
                           all_batches=all_batches)

@students_bp.route('/<int:student_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(student_id):
    student = Student.query.get_or_404(student_id)
    classes = Class.query.order_by(Class.name).all()
    batches = Batch.query.order_by(Batch.name).all()

    if request.method == 'POST':
        user = student.user
        user.first_name = request.form.get('first_name', '').strip()
        user.last_name = request.form.get('last_name', '').strip()
        user.email = request.form.get('email', '').strip()

        dob_str = request.form.get('dob')
        student.dob = datetime.strptime(dob_str, '%Y-%m-%d').date() if dob_str else None
        student.gender = request.form.get('gender')
        student.mobile = request.form.get('mobile', '').strip()
        student.address = request.form.get('address', '').strip()
        student.parent_name = request.form.get('parent_name', '').strip()
        student.parent_mobile = request.form.get('parent_mobile', '').strip()
        student.class_id = request.form.get('class_id', type=int)
        student.batch_id = request.form.get('batch_id', type=int)
        student.roll_number = request.form.get('roll_number', '').strip()
        student.status = request.form.get('status', 'active')

        db.session.commit()
        log_action('STUDENT_UPDATED', target_type='Student', target_id=student.id, details=f"Updated details for {student.full_name}")
        flash(f'Student details for "{student.full_name}" updated successfully.', 'success')
        return redirect(url_for('students.view', student_id=student.id))

    return render_template('students/form.html', student=student, classes=classes, batches=batches)

@students_bp.route('/<int:student_id>/disable', methods=['POST'])
@login_required
@admin_required
def disable(student_id):
    student = Student.query.get_or_404(student_id)
    student.user.is_active = False
    student.status = 'disabled'
    db.session.commit()
    log_action('STUDENT_DISABLED', target_type='Student', target_id=student.id, details=f"Disabled login for student '{student.full_name}' ({student.student_code})")
    flash(f'Account login for student "{student.full_name}" has been disabled. Historical records remain intact.', 'info')
    return redirect(url_for('students.view', student_id=student.id))

@students_bp.route('/<int:student_id>/enable', methods=['POST'])
@login_required
@admin_required
def enable(student_id):
    student = Student.query.get_or_404(student_id)
    student.user.is_active = True
    student.status = 'active'
    db.session.commit()
    log_action('STUDENT_ENABLED', target_type='Student', target_id=student.id, details=f"Re-enabled account for student '{student.full_name}' ({student.student_code})")
    flash(f'Account login for student "{student.full_name}" has been re-enabled.', 'success')
    return redirect(url_for('students.view', student_id=student.id))

@students_bp.route('/<int:student_id>/suspend', methods=['POST'])
@login_required
@teacher_required
def suspend(student_id):
    student = Student.query.get_or_404(student_id)
    reason = request.form.get('reason', '').strip()

    if not reason:
        flash('You must list a reason before suspending any student.', 'danger')
        return redirect(url_for('students.view', student_id=student.id))

    # Directly suspend student account
    student.user.is_active = False
    student.status = 'suspended'
    
    # Create notification for all Super Admin users
    from app.models import Notification
    super_admins = User.query.filter_by(role=Role.SUPER_ADMIN).all()
    for sa in super_admins:
        notif = Notification(
            user_id=sa.id,
            title='Student Suspended by Teacher',
            message=f"Teacher {current_user.full_name} suspended student {student.full_name} ({student.student_code}). Reason: {reason}",
            link=url_for('students.view', student_id=student.id)
        )
        db.session.add(notif)

    db.session.commit()
    log_action('STUDENT_SUSPENDED_BY_TEACHER', target_type='Student', target_id=student.id, details=f"Teacher {current_user.full_name} suspended {student.full_name}. Reason: {reason}")
    flash(f'Student "{student.full_name}" has been suspended. Reason logged and Super Admin notified.', 'warning')
    return redirect(url_for('students.view', student_id=student.id))

@students_bp.route('/<int:student_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete(student_id):
    student = Student.query.get_or_404(student_id)
    student_name = student.full_name
    student_code = student.student_code
    user = student.user

    # Require account to be disabled/suspended before permanent delete
    if user.is_active and student.status not in ['disabled', 'suspended', 'inactive']:
        flash(f'Cannot permanently delete active student "{student_name}". Please disable or block the account first.', 'danger')
        return redirect(url_for('students.view', student_id=student.id))

    db.session.delete(user)
    db.session.commit()

    log_action('STUDENT_PERMANENTLY_DELETED', target_type='Student', target_id=student_id, details=f"Super Admin permanently purged disabled student '{student_name}' ({student_code})")
    flash(f'Student account for "{student_name}" ({student_code}) permanently deleted from database.', 'warning')
    return redirect(url_for('students.index'))

@students_bp.route('/<int:student_id>/request-action', methods=['POST'])
@login_required
@teacher_required
def request_action(student_id):
    student = Student.query.get_or_404(student_id)
    teacher = current_user.teacher_profile
    request_type = request.form.get('request_type', 'suspension')  # deletion, suspension
    reason = request.form.get('reason', '').strip()

    if not reason:
        flash('Please provide a reason for the request.', 'warning')
        return redirect(url_for('students.view', student_id=student.id))

    if request_type == 'suspension':
        # Direct suspension for teachers
        return suspend(student_id)

    req = StudentRequest(
        student_id=student.id,
        requested_by_teacher_id=teacher.id if teacher else None,
        request_type=request_type,
        reason=reason,
        status='pending'
    )
    db.session.add(req)
    db.session.commit()

    log_action('TEACHER_STUDENT_REQUEST', target_type='Student', target_id=student.id, details=f"Teacher {current_user.full_name} submitted deletion request for Student '{student.full_name}'. Reason: {reason}")
    flash(f'Deletion request for student "{student.full_name}" submitted to Super Admin.', 'success')
    return redirect(url_for('students.view', student_id=student.id))

@students_bp.route('/requests')
@login_required
@admin_required
def requests_list():
    requests = StudentRequest.query.order_by(StudentRequest.created_at.desc()).all()
    return render_template('students/requests.html', requests=requests)

@students_bp.route('/request/<int:request_id>/process', methods=['POST'])
@login_required
@super_admin_required
def process_request(request_id):
    req = StudentRequest.query.get_or_404(request_id)
    action = request.form.get('action')  # approve, reject

    if action == 'approve':
        req.status = 'approved'
        req.processed_by_user_id = current_user.id
        req.processed_at = datetime.utcnow()

        student = req.student
        if req.request_type == 'deletion':
            student.user.is_active = False
            student.status = 'disabled'
            db.session.commit()
            log_action('STUDENT_REQUEST_APPROVED_DISABLE', target_type='StudentRequest', target_id=req.id, details=f"Approved deletion request (disabled account) for student {student.full_name}")
            flash(f'Approved request. Account for student "{student.full_name}" disabled (login blocked, records preserved).', 'success')
            return redirect(url_for('students.requests_list'))

        elif req.request_type == 'suspension':
            student.user.is_active = False
            student.status = 'suspended'
            db.session.commit()
            log_action('STUDENT_REQUEST_APPROVED_SUSPENSION', target_type='StudentRequest', target_id=req.id, details=f"Approved suspension request for student {student.full_name}")
            flash(f'Approved suspension request for student "{student.full_name}".', 'warning')

    elif action == 'reject':
        req.status = 'rejected'
        req.processed_by_user_id = current_user.id
        req.processed_at = datetime.utcnow()
        db.session.commit()
        flash('Request rejected.', 'info')

    return redirect(url_for('students.requests_list'))

@students_bp.route('/<int:student_id>/transfer-batch', methods=['POST'])
@login_required
@admin_required
def transfer_batch(student_id):
    student = Student.query.get_or_404(student_id)
    new_batch_id = request.form.get('new_batch_id', type=int)
    
    if new_batch_id:
        batch = Batch.query.get(new_batch_id)
        if batch:
            old_batch_name = student.batch.name if student.batch else "Unassigned"
            student.batch_id = batch.id
            db.session.commit()
            log_action('STUDENT_BATCH_TRANSFERRED', target_type='Student', target_id=student.id, details=f"Transferred {student.full_name} from {old_batch_name} to {batch.name}")
            flash(f'Student transferred to "{batch.name}" successfully.', 'success')

    return redirect(url_for('students.view', student_id=student.id))
