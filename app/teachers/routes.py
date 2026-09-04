from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.teachers import teachers_bp
from app.extensions import db
from app.models import Teacher, User, Role, Class, Batch, Subject, TeacherAssignment, Timetable
from app.utils.decorators import admin_required, super_admin_required
from app.services.audit_service import log_action

@teachers_bp.route('/')
@login_required
def index():
    search = request.args.get('search', '').strip()
    query = Teacher.query.join(User)

    if search:
        query = query.filter(
            (User.first_name.ilike(f'%{search}%')) |
            (User.last_name.ilike(f'%{search}%')) |
            (Teacher.teacher_code.ilike(f'%{search}%')) |
            (Teacher.specialization.ilike(f'%{search}%'))
        )

    teachers = query.order_by(User.first_name.asc()).all()
    return render_template('teachers/index.html', teachers=teachers, search=search)

@teachers_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', 'Teacher@123')
        mobile = request.form.get('mobile', '').strip()
        qualification = request.form.get('qualification', '').strip()
        specialization = request.form.get('specialization', '').strip()

        if User.query.filter_by(username=username).first():
            flash('Username already exists. Choose a different username.', 'danger')
            return render_template('teachers/form.html')

        if User.query.filter_by(email=email).first():
            flash('Email already exists. Choose a different email.', 'danger')
            return render_template('teachers/form.html')

        seq = Teacher.query.count() + 1
        teacher_code = f"TCH-{seq:03d}"

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=Role.TEACHER,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        teacher = Teacher(
            user_id=user.id,
            teacher_code=teacher_code,
            mobile=mobile,
            qualification=qualification,
            specialization=specialization,
            joining_date=datetime.utcnow().date(),
            employment_status='active'
        )
        db.session.add(teacher)
        db.session.commit()

        log_action('TEACHER_ADDED', target_type='Teacher', target_id=teacher.id, details=f"Added teacher {teacher.full_name} ({teacher.teacher_code})")
        flash(f'Teacher "{teacher.full_name}" registered successfully with Code: {teacher.teacher_code}', 'success')
        return redirect(url_for('teachers.view', teacher_id=teacher.id))

    return render_template('teachers/form.html')

@teachers_bp.route('/<int:teacher_id>')
@login_required
def view(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    
    if current_user.is_teacher() and (not current_user.teacher_profile or current_user.teacher_profile.id != teacher.id):
        flash('You do not have permission to view other teachers\' private profiles.', 'danger')
        return redirect(url_for('dashboard.index'))

    assignments = TeacherAssignment.query.filter_by(teacher_id=teacher.id).all()
    timetables = Timetable.query.filter_by(teacher_id=teacher.id).order_by(Timetable.day_of_week, Timetable.start_time).all()
    classes = Class.query.order_by(Class.name).all()
    batches = Batch.query.order_by(Batch.name).all()
    subjects = Subject.query.order_by(Subject.name).all()

    return render_template('teachers/view.html',
                           teacher=teacher,
                           assignments=assignments,
                           timetables=timetables,
                           classes=classes,
                           batches=batches,
                           subjects=subjects)

@teachers_bp.route('/<int:teacher_id>/disable', methods=['POST'])
@login_required
@super_admin_required
def disable(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    teacher.user.is_active = False
    teacher.employment_status = 'resigned'
    db.session.commit()
    log_action('TEACHER_DISABLED', target_type='Teacher', target_id=teacher.id, details=f"Disabled login for teacher '{teacher.full_name}' ({teacher.teacher_code})")
    flash(f'Teacher account for "{teacher.full_name}" disabled. Login access blocked.', 'info')
    return redirect(url_for('teachers.view', teacher_id=teacher.id))

@teachers_bp.route('/<int:teacher_id>/enable', methods=['POST'])
@login_required
@super_admin_required
def enable(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    teacher.user.is_active = True
    teacher.employment_status = 'active'
    db.session.commit()
    log_action('TEACHER_ENABLED', target_type='Teacher', target_id=teacher.id, details=f"Re-enabled login for teacher '{teacher.full_name}' ({teacher.teacher_code})")
    flash(f'Teacher account for "{teacher.full_name}" re-enabled.', 'success')
    return redirect(url_for('teachers.view', teacher_id=teacher.id))

@teachers_bp.route('/<int:teacher_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    teacher_name = teacher.full_name
    teacher_code = teacher.teacher_code
    user = teacher.user

    if user.is_active and teacher.employment_status not in ['resigned', 'disabled']:
        flash(f'Cannot permanently delete active teacher "{teacher_name}". Please disable the account first.', 'danger')
        return redirect(url_for('teachers.view', teacher_id=teacher.id))

    db.session.delete(user)
    db.session.commit()

    log_action('TEACHER_PERMANENTLY_DELETED', target_type='Teacher', target_id=teacher_id, details=f"Super Admin permanently deleted teacher account '{teacher_name}' ({teacher_code})")
    flash(f'Teacher account for "{teacher_name}" ({teacher_code}) permanently purged from database.', 'warning')
    return redirect(url_for('teachers.index'))

@teachers_bp.route('/<int:teacher_id>/assign', methods=['POST'])
@login_required
@admin_required
def assign_subject(teacher_id):
    teacher = Teacher.query.get_or_404(teacher_id)
    class_id = request.form.get('class_id', type=int)
    batch_id = request.form.get('batch_id', type=int)
    subject_id = request.form.get('subject_id', type=int)

    if class_id and batch_id and subject_id:
        existing = TeacherAssignment.query.filter_by(
            teacher_id=teacher.id,
            batch_id=batch_id,
            subject_id=subject_id
        ).first()

        if existing:
            flash('Teacher is already assigned to this batch and subject.', 'warning')
        else:
            assignment = TeacherAssignment(
                teacher_id=teacher.id,
                class_id=class_id,
                batch_id=batch_id,
                subject_id=subject_id
            )
            db.session.add(assignment)
            db.session.commit()
            log_action('TEACHER_ASSIGNMENT_CREATED', target_type='TeacherAssignment', target_id=assignment.id, details=f"Assigned {teacher.full_name} to Batch {batch_id}")
            flash('Teaching assignment added successfully.', 'success')

    return redirect(url_for('teachers.view', teacher_id=teacher.id))

@teachers_bp.route('/assignment/<int:assignment_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_assignment(assignment_id):
    assignment = TeacherAssignment.query.get_or_404(assignment_id)
    teacher_id = assignment.teacher_id
    db.session.delete(assignment)
    db.session.commit()
    flash('Teaching assignment removed.', 'info')
    return redirect(url_for('teachers.view', teacher_id=teacher_id))
