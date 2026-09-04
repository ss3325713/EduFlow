from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.teachers import teachers_bp
from app.extensions import db
from app.models import Teacher, User, Role, Class, Batch, Subject, TeacherAssignment, Timetable, Student, Parent, StudentParent

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

# ----------------------------------------------------
# Teacher → Parent Email Communication System
# ----------------------------------------------------

PREDEFINED_EMAIL_TEMPLATES = {
    'academic_concern': {
        'title': 'Academic Concern Notice',
        'subject': 'Academic Update regarding {{ student_name }}',
        'body': 'I am writing to share a brief update regarding {{ student_name }}\'s recent academic progress in {{ subject }}. We have noticed some areas where additional attention and practice would be beneficial.'
    },
    'attendance_concern': {
        'title': 'Attendance & Punctuality Notice',
        'subject': 'Attendance Concern: {{ student_name }}',
        'body': 'This is an attendance alert regarding {{ student_name }}\'s recent absences in {{ batch_name }}. Consistent attendance is crucial for maintaining academic standing in {{ subject }}.'
    },
    'homework_reminder': {
        'title': 'Homework Assignment Reminder',
        'subject': 'Pending Homework Assignment for {{ student_name }}',
        'body': 'Please be reminded that {{ student_name }} has a pending homework assignment for {{ subject }} in {{ batch_name }}. Kindly ensure it is completed and submitted on time.'
    },
    'performance_appreciation': {
        'title': 'Performance Appreciation Note',
        'subject': 'Commendable Performance: {{ student_name }}',
        'body': 'I am pleased to inform you of {{ student_name }}\'s excellent performance and active participation in {{ subject }}. Keep up the fantastic effort!'
    },
    'ptm_request': {
        'title': 'Parent-Teacher Meeting Request',
        'subject': 'Parent-Teacher Meeting Request for {{ student_name }}',
        'body': 'I would like to invite you for a brief Parent-Teacher discussion regarding {{ student_name }}\'s overall development and academic goals in {{ class_name }}.'
    },
    'general_update': {
        'title': 'General Class Update',
        'subject': 'Class Update from {{ teacher_name }} ({{ subject }})',
        'body': 'Dear {{ parent_name }},\n\nHere is an important update regarding our upcoming sessions in {{ batch_name }}.'
    }
}

def get_teacher_authorized_students(user):
    """Helper returning students authorized for the logged in teacher, or all students if Admin/Super Admin."""
    if user.is_admin():
        return Student.query.join(User).filter(User.is_active == True).all()

    if not user.is_teacher() or not user.teacher_profile:
        return []

    teacher = user.teacher_profile
    # Collect batch IDs from assignments and timetable
    assigned_batch_ids = set()
    for a in TeacherAssignment.query.filter_by(teacher_id=teacher.id).all():
        if a.batch_id:
            assigned_batch_ids.add(a.batch_id)
    for t in Timetable.query.filter_by(teacher_id=teacher.id).all():
        if t.batch_id:
            assigned_batch_ids.add(t.batch_id)

    if not assigned_batch_ids:
        return []

    return Student.query.filter(Student.batch_id.in_(list(assigned_batch_ids))).join(User).filter(User.is_active == True).all()

@teachers_bp.route('/email/compose', methods=['GET', 'POST'])
@login_required
def compose_email():
    if not (current_user.is_teacher() or current_user.is_admin()):
        flash('Permission denied. Only teachers and administrators can send parent emails.', 'danger')
        return redirect(url_for('dashboard.index'))

    authorized_students = get_teacher_authorized_students(current_user)
    authorized_student_ids = [s.id for s in authorized_students]

    # Map student to their linked parents
    student_parent_map = {}
    for student in authorized_students:
        parents = []
        for link in student.parent_links:
            if link.parent and link.parent.user and link.parent.user.email:
                parents.append({
                    'id': link.parent.id,
                    'name': link.parent.full_name,
                    'email': link.parent.user.email,
                    'relationship': link.relationship or 'parent'
                })
        student_parent_map[student.id] = parents

    if request.method == 'POST':
        action = request.form.get('action', 'send')
        student_id = request.form.get('student_id', type=int)
        parent_id = request.form.get('parent_id', type=int)
        template_key = request.form.get('template_key', 'general_update')
        subject = request.form.get('subject', '').strip()
        custom_message = request.form.get('message', '').strip()

        # Strict Backend Scope Verification
        student = Student.query.get(student_id) if student_id else None
        if not student or student.id not in authorized_student_ids:
            flash('Permission Denied: You are not authorized to email parents of this student.', 'danger')
            return render_template('teachers/compose_email.html',
                                   students=authorized_students,
                                   student_parent_map=student_parent_map,
                                   templates=PREDEFINED_EMAIL_TEMPLATES)

        # Verify parent linked to student
        parent = None
        if parent_id:
            parent_link = StudentParent.query.filter_by(student_id=student.id, parent_id=parent_id).first()
            if parent_link:
                parent = parent_link.parent

        if not parent or not parent.user or not parent.user.email:
            flash('Selected student does not have a linked parent with a valid email address.', 'warning')
            return render_template('teachers/compose_email.html',
                                   students=authorized_students,
                                   student_parent_map=student_parent_map,
                                   templates=PREDEFINED_EMAIL_TEMPLATES)

        from app.models import EmailCategory, InstituteSettings
        from app.services.email_service import EmailService

        institute = InstituteSettings.get_settings()
        teacher_profile = current_user.teacher_profile
        teacher_designation = teacher_profile.qualification if teacher_profile and teacher_profile.qualification else 'Faculty Member'
        teacher_subject = teacher_profile.specialization if teacher_profile and teacher_profile.specialization else 'Academic Subject'

        context = {
            'student_name': student.full_name,
            'parent_name': parent.full_name,
            'teacher_name': current_user.full_name,
            'teacher_designation': teacher_designation,
            'subject': teacher_subject,
            'batch_name': student.batch.name if student.batch else 'General Batch',
            'class_name': student.academic_class.name if student.academic_class else 'General Class',
            'institute_name': institute.name if institute else 'EduFlow Academy',
            'academic_session': institute.academic_session if institute else '2026-2027',
            'date': datetime.utcnow().strftime('%B %d, %Y'),
            'message': custom_message,
            'template_title': PREDEFINED_EMAIL_TEMPLATES.get(template_key, {}).get('title', 'Faculty Notice')
        }

        if action == 'preview':
            return render_template('teachers/compose_email.html',
                                   students=authorized_students,
                                   student_parent_map=student_parent_map,
                                   templates=PREDEFINED_EMAIL_TEMPLATES,
                                   preview=True,
                                   preview_subject=subject,
                                   preview_context=context,
                                   selected_student_id=student_id,
                                   selected_parent_id=parent_id,
                                   selected_template=template_key,
                                   custom_message=custom_message)

        # Dispatch Email
        success, msg = EmailService.send_email(
            to_email=parent.user.email,
            subject=subject or f"Faculty Notice regarding {student.full_name}",
            template_name='teacher_parent_email',
            context=context,
            reply_to=current_user.email,
            category=EmailCategory.COMMUNICATION,
            user_id=parent.user.id
        )

        log_action('TEACHER_EMAIL_SENT', target_type='User', target_id=parent.user.id, details=f"Teacher {current_user.full_name} emailed parent {parent.full_name} re student {student.full_name}")
        flash(f'Email notification successfully sent to {parent.full_name} ({parent.user.email}).', 'success')
        return redirect(url_for('teachers.compose_email'))

    return render_template('teachers/compose_email.html',
                           students=authorized_students,
                           student_parent_map=student_parent_map,
                           templates=PREDEFINED_EMAIL_TEMPLATES)

