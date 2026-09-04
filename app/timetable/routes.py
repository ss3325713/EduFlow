from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.timetable import timetable_bp
from app.extensions import db
from app.models import Timetable, DayOfWeek, Class, Batch, Subject, Teacher
from app.utils.decorators import admin_required
from app.services.timetable_service import TimetableService

@timetable_bp.route('/')
@login_required
def index():
    batch_id = request.args.get('batch_id', type=int)
    teacher_id = request.args.get('teacher_id', type=int)

    batches = Batch.query.order_by(Batch.name).all()
    teachers = Teacher.query.join(Teacher.user).order_by(Teacher.id).all()

    query = Timetable.query

    if current_user.is_student() and current_user.student_profile and current_user.student_profile.batch_id:
        batch_id = current_user.student_profile.batch_id

    if current_user.is_teacher() and current_user.teacher_profile and not teacher_id:
        teacher_id = current_user.teacher_profile.id

    if batch_id:
        query = query.filter_by(batch_id=batch_id)
    elif teacher_id:
        query = query.filter_by(teacher_id=teacher_id)

    entries = query.order_by(Timetable.start_time.asc()).all()

    # Organize entries by Day of Week
    schedule_matrix = {day: [] for day in DayOfWeek.DAYS}
    for entry in entries:
        if entry.day_of_week in schedule_matrix:
            schedule_matrix[entry.day_of_week].append(entry)

    return render_template('timetable/index.html',
                           schedule_matrix=schedule_matrix,
                           days=DayOfWeek.DAYS,
                           batches=batches,
                           teachers=teachers,
                           selected_batch=batch_id,
                           selected_teacher=teacher_id)

@timetable_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    classes = Class.query.order_by(Class.name).all()
    batches = Batch.query.order_by(Batch.name).all()
    subjects = Subject.query.order_by(Subject.name).all()
    teachers = Teacher.query.join(Teacher.user).order_by(Teacher.id).all()

    if request.method == 'POST':
        day_of_week = request.form.get('day_of_week')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        class_id = request.form.get('class_id', type=int)
        batch_id = request.form.get('batch_id', type=int)
        subject_id = request.form.get('subject_id', type=int)
        teacher_id = request.form.get('teacher_id', type=int)
        room_number = request.form.get('room_number', 'Room 101').strip()

        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()

        if start_time >= end_time:
            flash('End time must be after start time.', 'danger')
            return render_template('timetable/form.html', days=DayOfWeek.DAYS, classes=classes, batches=batches, subjects=subjects, teachers=teachers)

        # Validate schedule collisions
        is_valid, error_msg = TimetableService.validate_schedule(
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            teacher_id=teacher_id,
            batch_id=batch_id
        )

        if not is_valid:
            flash(f"Scheduling Conflict: {error_msg}", 'danger')
            return render_template('timetable/form.html', days=DayOfWeek.DAYS, classes=classes, batches=batches, subjects=subjects, teachers=teachers)

        entry = Timetable(
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            class_id=class_id,
            batch_id=batch_id,
            subject_id=subject_id,
            teacher_id=teacher_id,
            room_number=room_number
        )
        db.session.add(entry)
        db.session.commit()

        flash('Timetable slot scheduled successfully.', 'success')
        return redirect(url_for('timetable.index', batch_id=batch_id))

    return render_template('timetable/form.html',
                           days=DayOfWeek.DAYS,
                           classes=classes,
                           batches=batches,
                           subjects=subjects,
                           teachers=teachers)

@timetable_bp.route('/<int:entry_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete(entry_id):
    entry = Timetable.query.get_or_404(entry_id)
    batch_id = entry.batch_id

    # Collect class slot metadata before deleting
    context = {
        'class_name': entry.academic_class.name if entry.academic_class else 'Class',
        'batch_name': entry.batch.name if entry.batch else 'Batch',
        'subject_name': entry.subject.name if entry.subject else 'Subject',
        'teacher_name': entry.teacher.full_name if entry.teacher else 'Faculty Member',
        'day_of_week': entry.day_of_week,
        'start_time': entry.start_time.strftime('%H:%M'),
        'end_time': entry.end_time.strftime('%H:%M'),
        'room_number': entry.room_number or 'Unspecified',
        'event_type': 'Class Cancelled',
        'reason': 'Scheduled slot has been cancelled by administration.'
    }

    db.session.delete(entry)
    db.session.commit()

    # ----------------------------------------------------
    # Email Notification Integration for Class Cancellation
    # ----------------------------------------------------
    try:
        from app.models import Student, EmailCategory
        from app.services.email_service import EmailService

        students = Student.query.filter_by(batch_id=batch_id).all()
        recipients = set()
        for st in students:
            if st.user and st.user.email:
                recipients.add((st.user.email, st.user.id))
            for link in st.parent_links:
                if link.parent and link.parent.user and link.parent.user.email:
                    recipients.add((link.parent.user.email, link.parent.user.id))

        for email_addr, u_id in recipients:
            EmailService.send_email(
                to_email=email_addr,
                subject=f"Class Cancellation Alert: {context['subject_name']} ({context['batch_name']})",
                template_name='class_rescheduled',
                context=context,
                category=EmailCategory.CLASS,
                user_id=u_id
            )
    except Exception as err:
        pass

    flash('Timetable slot deleted.', 'info')
    return redirect(url_for('timetable.index', batch_id=batch_id))

