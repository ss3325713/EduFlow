from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.announcements import announcements_bp
from app.extensions import db
from app.models import Announcement, Class, Batch
from app.utils.decorators import admin_required

@announcements_bp.route('/')
@login_required
def index():
    query = Announcement.query.order_by(Announcement.publish_date.desc())

    if current_user.is_teacher():
        # Teachers see general/teacher notices AND notices created by themselves or for their assigned batches
        query = query.filter(
            (Announcement.target_role.in_(['all', 'teacher'])) |
            (Announcement.created_by_user_id == current_user.id)
        )
    elif current_user.is_student() and current_user.student_profile:
        student = current_user.student_profile
        query = query.filter(
            (Announcement.target_role.in_(['all', 'student'])) |
            (Announcement.batch_id == student.batch_id) |
            (Announcement.class_id == student.class_id)
        )
    elif current_user.is_parent() and current_user.parent_profile:
        linked_batch_ids = [st.batch_id for st in current_user.parent_profile.linked_students if st.batch_id]
        linked_class_ids = [st.class_id for st in current_user.parent_profile.linked_students if st.class_id]
        query = query.filter(
            (Announcement.target_role.in_(['all', 'parent'])) |
            (Announcement.batch_id.in_(linked_batch_ids)) |
            (Announcement.class_id.in_(linked_class_ids))
        )

    announcements = query.all()
    return render_template('announcements/index.html', announcements=announcements)

@announcements_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if not (current_user.is_admin() or current_user.is_teacher()):
        flash('Permission denied. Only faculty and administrators can publish announcements.', 'danger')
        return redirect(url_for('announcements.index'))

    classes = Class.query.order_by(Class.name).all()
    batches = Batch.query.order_by(Batch.name).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        target_role = request.form.get('target_role', 'all')
        class_id = request.form.get('class_id', type=int)
        batch_id = request.form.get('batch_id', type=int)
        priority = request.form.get('priority', 'normal')

        batch = Batch.query.get(batch_id) if batch_id else None
        if batch and class_id and batch.class_id != class_id:
            flash('Selected batch does not belong to the selected class.', 'danger')
            return render_template('announcements/form.html', classes=classes, batches=batches)

        announcement = Announcement(
            title=title,
            content=content,
            target_role=target_role,
            class_id=class_id if class_id else None,
            batch_id=batch_id if batch_id else None,
            priority=priority,
            publish_date=datetime.utcnow(),
            created_by_user_id=current_user.id
        )
        db.session.add(announcement)
        db.session.commit()

        # ----------------------------------------------------
        # Email Notification Integration for Announcements
        # ----------------------------------------------------
        try:
            from app.models import User, Role, Student, Parent, EmailCategory
            from app.services.email_service import EmailService

            recipient_users = set()
            query = User.query.filter_by(is_active=True)

            if target_role == 'student':
                query = query.filter_by(role=Role.STUDENT)
            elif target_role == 'teacher':
                query = query.filter_by(role=Role.TEACHER)
            elif target_role == 'parent':
                query = query.filter_by(role=Role.PARENT)

            users_pool = query.all()

            for u in users_pool:
                if not u.email:
                    continue
                # Apply class/batch filtering
                if batch_id and u.is_student() and u.student_profile and u.student_profile.batch_id != batch_id:
                    continue
                if class_id and u.is_student() and u.student_profile and u.student_profile.class_id != class_id:
                    continue
                recipient_users.add(u)

            context = {
                'announcement': announcement,
                'date': datetime.utcnow().strftime('%B %d, %Y')
            }

            for recipient in recipient_users:
                EmailService.send_email(
                    to_email=recipient.email,
                    subject=f"Notice: {announcement.title}",
                    template_name='announcement_email',
                    context=context,
                    category=EmailCategory.INSTITUTIONAL,
                    user_id=recipient.id
                )
        except Exception as err:
            current_app.logger.error(f"Error sending announcement emails: {err}")

        flash(f'Announcement "{announcement.title}" published successfully.', 'success')
        return redirect(url_for('announcements.index'))

    return render_template('announcements/form.html', classes=classes, batches=batches)

