import logging
from datetime import datetime, date, timedelta
from flask import current_app, url_for
from app.extensions import db
from app.models import (
    TeacherRequest, Teacher, Timetable, Class, Batch, Subject,
    TeacherAssignment, TeacherAttendance, Student, Notification, EmailCategory
)
from app.services.audit_service import log_action
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

def get_app_base_url():
    if current_app and current_app.config.get('TESTING'):
        return current_app.config.get('APP_BASE_URL', 'http://localhost:5000').rstrip('/')
    base_url = current_app.config.get('APP_BASE_URL') if current_app else 'https://skillbasis.online'
    return base_url.rstrip('/') if base_url else 'https://skillbasis.online'

class RequestService:

    @staticmethod
    def create_request(teacher_id, category, title, description, **kwargs):
        teacher = db.session.get(Teacher, teacher_id)
        if not teacher:
            raise ValueError("Invalid teacher ID.")

        category = category.lower().strip()
        if category not in ['leave', 'schedule_change', 'batch_allocation', 'new_class', 'other']:
            raise ValueError("Invalid request category.")

        req = TeacherRequest(
            teacher_id=teacher_id,
            request_type=category,
            title=title.strip(),
            description=description.strip(),
            status='pending'
        )

        if category == 'leave':
            start_date = kwargs.get('start_date')
            end_date = kwargs.get('end_date')
            if not start_date or not end_date:
                raise ValueError("Start date and end date are required for leave requests.")
            if isinstance(start_date, str):
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            if isinstance(end_date, str):
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
            if start_date > end_date:
                raise ValueError("Start date cannot be after end date.")

            # Validate overlapping pending/approved leave requests
            existing_overlap = TeacherRequest.query.filter(
                TeacherRequest.teacher_id == teacher_id,
                TeacherRequest.request_type == 'leave',
                TeacherRequest.status.in_(['pending', 'under_review', 'approved']),
                TeacherRequest.start_date <= end_date,
                TeacherRequest.end_date >= start_date
            ).first()
            if existing_overlap:
                raise ValueError(f"You already have an existing leave request ({existing_overlap.status.title()}) overlapping with these dates ({existing_overlap.start_date} to {existing_overlap.end_date}).")

            req.start_date = start_date
            req.end_date = end_date

        elif category == 'schedule_change':
            timetable_id = kwargs.get('timetable_id')
            change_action = kwargs.get('change_action', 'change_time')
            proposed_date = kwargs.get('proposed_date')
            proposed_time = kwargs.get('proposed_time')

            timetable = db.session.get(Timetable, timetable_id)
            if not timetable:
                raise ValueError("Invalid scheduled class selected.")
            if timetable.teacher_id != teacher_id:
                raise ValueError("You can only request schedule changes for classes assigned to you.")

            req.timetable_id = timetable_id
            req.change_action = change_action

            if proposed_date:
                req.proposed_date = datetime.strptime(proposed_date, '%Y-%m-%d').date() if isinstance(proposed_date, str) else proposed_date
            if proposed_time:
                req.proposed_time = datetime.strptime(proposed_time, '%H:%M').time() if isinstance(proposed_time, str) else proposed_time

        elif category == 'batch_allocation':
            target_class_id = kwargs.get('target_class_id')
            target_batch_id = kwargs.get('target_batch_id')
            target_subject_id = kwargs.get('target_subject_id')
            allocation_action = kwargs.get('allocation_action', 'assign')

            if not target_class_id or not target_batch_id or not target_subject_id:
                raise ValueError("Class, Batch, and Subject selection are required.")

            req.target_class_id = target_class_id
            req.target_batch_id = target_batch_id
            req.target_subject_id = target_subject_id
            req.allocation_action = allocation_action

        elif category == 'new_class':
            target_class_id = kwargs.get('target_class_id')
            target_batch_id = kwargs.get('target_batch_id')
            target_subject_id = kwargs.get('target_subject_id')
            proposed_date = kwargs.get('proposed_date')
            proposed_time = kwargs.get('proposed_time')
            duration_minutes = kwargs.get('duration_minutes', 60)

            if not target_class_id or not target_batch_id or not target_subject_id or not proposed_date or not proposed_time:
                raise ValueError("Class, Batch, Subject, Proposed Date, and Proposed Time are required.")

            req.target_class_id = target_class_id
            req.target_batch_id = target_batch_id
            req.target_subject_id = target_subject_id
            req.proposed_date = datetime.strptime(proposed_date, '%Y-%m-%d').date() if isinstance(proposed_date, str) else proposed_date
            req.proposed_time = datetime.strptime(proposed_time, '%H:%M').time() if isinstance(proposed_time, str) else proposed_time
            req.duration_minutes = int(duration_minutes)

        elif category == 'other':
            req.attachment_path = kwargs.get('attachment_path')

        db.session.add(req)
        db.session.commit()

        log_action('TEACHER_REQUEST_CREATED', target_type='TeacherRequest', target_id=req.id,
                   details=f"Teacher {teacher.full_name} submitted a {category.replace('_', ' ').title()} request (ID: #{req.id})")

        # Send notification to super admins
        try:
            from app.models import User, Role
            admins = User.query.filter(User.role.in_([Role.SUPER_ADMIN, Role.ADMIN])).all()
            for admin in admins:
                notif = Notification(
                    user_id=admin.id,
                    title=f"New Teacher Request #{req.id}",
                    message=f"{teacher.full_name} submitted a {category.replace('_', ' ').title()} request.",
                    link=url_for('requests.admin_index')
                )
                db.session.add(notif)
            db.session.commit()
        except Exception as err:
            logger.warning(f"Failed to create admin notification for request #{req.id}: {err}")

        return req

    @staticmethod
    def process_request(request_id, status, admin_user, admin_response=None):
        req = db.session.get(TeacherRequest, request_id)
        if not req:
            raise ValueError("Request not found.")

        status = status.lower().strip()
        if status not in ['approved', 'rejected', 'under_review', 'completed']:
            raise ValueError("Invalid request status.")

        req.status = status
        req.admin_response = admin_response.strip() if admin_response else None
        req.processed_by_user_id = admin_user.id
        req.processed_at = datetime.utcnow()

        affected_info = {}

        if status == 'approved':
            # Execute automated actions based on category
            if req.request_type == 'leave':
                affected_info = RequestService._execute_leave_approval(req)

            elif req.request_type == 'schedule_change':
                affected_info = RequestService._execute_schedule_change_approval(req)

            elif req.request_type == 'batch_allocation':
                affected_info = RequestService._execute_batch_allocation_approval(req)

            elif req.request_type == 'new_class':
                affected_info = RequestService._execute_new_class_approval(req)

        db.session.commit()

        log_action(f'TEACHER_REQUEST_{status.upper()}', target_type='TeacherRequest', target_id=req.id,
                   details=f"Admin {admin_user.full_name} marked request #{req.id} as '{status.title()}'")

        # Send notification & email to teacher
        try:
            teacher_user = req.teacher.user if req.teacher else None
            if teacher_user:
                notif = Notification(
                    user_id=teacher_user.id,
                    title=f"Request #{req.id} {status.title()}",
                    message=f"Your request '{req.title}' has been {status}. Admin note: {req.admin_response or 'No notes'}",
                    link=url_for('teachers.my_requests')
                )
                db.session.add(notif)
                db.session.commit()

                EmailService.send_email(
                    to_email=teacher_user.email,
                    subject=f"Teacher Request #{req.id} Update — SkillBasis",
                    template_name='request_status_update',
                    context={
                        'user': teacher_user,
                        'request': req,
                        'status': status.title(),
                        'admin_response': req.admin_response or 'Processed by Administrator'
                    },
                    category=EmailCategory.GENERAL_NOTIFICATION,
                    user_id=teacher_user.id
                )
        except Exception as mail_err:
            logger.warning(f"Failed to send teacher request notification email: {mail_err}")

        return req, affected_info

    @staticmethod
    def edit_approved_request(request_id, form_data, admin_user):
        req = db.session.get(TeacherRequest, request_id)
        if not req:
            raise ValueError("Request not found.")

        old_teacher_id = req.teacher_id
        old_status = req.status
        old_batch_id = req.target_batch_id or (req.timetable.batch_id if req.timetable else None)
        old_class_id = req.target_class_id or (req.timetable.class_id if req.timetable else None)

        # Update teacher assignment if provided
        teacher_id = form_data.get('teacher_id')
        if teacher_id:
            try:
                t_id = int(teacher_id)
                if t_id > 0:
                    t_obj = db.session.get(Teacher, t_id)
                    if not t_obj:
                        raise ValueError("Selected teacher does not exist.")
                    req.teacher_id = t_id
            except (ValueError, TypeError) as ve:
                if "Selected teacher" in str(ve):
                    raise ve

        status = form_data.get('status', '').strip().lower()
        if status and status in ['approved', 'rejected', 'pending', 'under_review', 'completed']:
            req.status = status

        admin_response = form_data.get('admin_response', '').strip()
        if admin_response:
            req.admin_response = admin_response

        # Target class, batch, subject
        class_id = form_data.get('target_class_id')
        if class_id is not None and str(class_id).isdigit():
            req.target_class_id = int(class_id) if int(class_id) > 0 else None

        batch_id = form_data.get('target_batch_id')
        if batch_id is not None and str(batch_id).isdigit():
            req.target_batch_id = int(batch_id) if int(batch_id) > 0 else None

        subject_id = form_data.get('target_subject_id')
        if subject_id is not None and str(subject_id).isdigit():
            req.target_subject_id = int(subject_id) if int(subject_id) > 0 else None

        # Actions
        change_action = form_data.get('change_action', '').strip()
        if change_action:
            req.change_action = change_action

        allocation_action = form_data.get('allocation_action', '').strip()
        if allocation_action:
            req.allocation_action = allocation_action

        # Dates & times
        start_date_str = form_data.get('start_date', '').strip()
        if start_date_str:
            req.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()

        end_date_str = form_data.get('end_date', '').strip()
        if end_date_str:
            req.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        proposed_date_str = form_data.get('proposed_date', '').strip()
        if proposed_date_str:
            req.proposed_date = datetime.strptime(proposed_date_str, '%Y-%m-%d').date()

        proposed_time_str = form_data.get('proposed_time', '').strip()
        if proposed_time_str:
            for fmt in ('%H:%M', '%H:%M:%S'):
                try:
                    req.proposed_time = datetime.strptime(proposed_time_str, fmt).time()
                    break
                except ValueError:
                    pass

        req.processed_by_user_id = admin_user.id
        req.processed_at = datetime.utcnow()

        affected_info = {}

        if req.status == 'approved':
            if req.request_type == 'leave':
                affected_info = RequestService._execute_leave_approval(req)

            elif req.request_type == 'schedule_change':
                if req.timetable:
                    req.timetable.teacher_id = req.teacher_id
                affected_info = RequestService._execute_schedule_change_approval(req)

            elif req.request_type == 'batch_allocation':
                affected_info = RequestService._execute_batch_allocation_approval(req)

            elif req.request_type == 'new_class':
                if req.timetable_id:
                    tt = db.session.get(Timetable, req.timetable_id)
                    if tt:
                        tt.teacher_id = req.teacher_id
                        if req.target_class_id: tt.class_id = req.target_class_id
                        if req.target_batch_id: tt.batch_id = req.target_batch_id
                        if req.target_subject_id: tt.subject_id = req.target_subject_id
                        if req.proposed_date:
                            tt.original_date = req.proposed_date
                            tt.day_of_week = req.proposed_date.strftime('%A')
                        if req.proposed_time:
                            tt.original_time = req.proposed_time
                            tt.start_time = req.proposed_time
                else:
                    affected_info = RequestService._execute_new_class_approval(req)

        db.session.commit()

        log_action('TEACHER_REQUEST_EDITED', target_type='TeacherRequest', target_id=req.id,
                   details=f"Admin {admin_user.full_name} edited request #{req.id} (Status: {req.status}, Teacher ID: {req.teacher_id})")

        # 1. Email & Notify current teacher
        current_teacher = db.session.get(Teacher, req.teacher_id)
        if current_teacher and current_teacher.user:
            try:
                notif = Notification(
                    user_id=current_teacher.user.id,
                    title=f"Request #{req.id} Modified by Admin",
                    message=f"Admin {admin_user.full_name} updated your request '{req.title}'. Status: {req.status.title()}. Remarks: {req.admin_response or 'No remarks'}",
                    link=url_for('teachers.my_requests')
                )
                db.session.add(notif)
                db.session.commit()

                EmailService.send_email(
                    to_email=current_teacher.user.email,
                    subject=f"Notice: Teacher Request #{req.id} Modified — SkillBasis",
                    template_name='request_edited',
                    context={
                        'user': current_teacher.user,
                        'request': req,
                        'admin_response': req.admin_response,
                        'message_intro': f"An administrator ({admin_user.full_name}) has updated the approval details for your request '{req.title}'."
                    },
                    category=EmailCategory.GENERAL_NOTIFICATION,
                    user_id=current_teacher.user.id
                )
            except Exception as err:
                logger.warning(f"Failed to send update email to teacher {current_teacher.id}: {err}")

        # If teacher reassigned, notify old teacher as well
        if old_teacher_id and old_teacher_id != req.teacher_id:
            old_t = db.session.get(Teacher, old_teacher_id)
            if old_t and old_t.user:
                try:
                    notif = Notification(
                        user_id=old_t.user.id,
                        title=f"Request #{req.id} Reassigned",
                        message=f"Request '{req.title}' has been reassigned to another faculty member by an administrator.",
                        link=url_for('teachers.my_requests')
                    )
                    db.session.add(notif)
                    db.session.commit()

                    EmailService.send_email(
                        to_email=old_t.user.email,
                        subject=f"Notice: Teacher Request #{req.id} Reassigned — SkillBasis",
                        template_name='request_edited',
                        context={
                            'user': old_t.user,
                            'request': req,
                            'admin_response': req.admin_response,
                            'message_intro': f"An administrator ({admin_user.full_name}) has updated Request #{req.id} and reassigned it."
                        },
                        category=EmailCategory.GENERAL_NOTIFICATION,
                        user_id=old_t.user.id
                    )
                except Exception as err:
                    logger.warning(f"Failed to send email to former teacher {old_teacher_id}: {err}")

        # 2. Email & Notify students of affected Batch / Class
        new_batch_id = req.target_batch_id or (req.timetable.batch_id if req.timetable else None)
        new_class_id = req.target_class_id or (req.timetable.class_id if req.timetable else None)

        relevant_batch_ids = {b for b in [new_batch_id, old_batch_id] if b}
        relevant_class_ids = {c for c in [new_class_id, old_class_id] if c}

        if req.request_type == 'leave':
            teacher_tts = Timetable.query.filter_by(teacher_id=req.teacher_id).all()
            for tt in teacher_tts:
                if tt.batch_id: relevant_batch_ids.add(tt.batch_id)
                if tt.class_id: relevant_class_ids.add(tt.class_id)

        students = []
        if relevant_batch_ids or relevant_class_ids:
            filters = []
            if relevant_batch_ids:
                filters.append(Student.batch_id.in_(list(relevant_batch_ids)))
            if relevant_class_ids:
                filters.append(Student.class_id.in_(list(relevant_class_ids)))
            students = Student.query.filter(Student.status == 'active', db.or_(*filters)).all()

        students_notified_count = 0
        for student in students:
            if student.user and student.user.email:
                try:
                    notif = Notification(
                        user_id=student.user.id,
                        title=f"Class Update: {req.title}",
                        message=f"An administrative update was made to a request for your batch/class schedule.",
                        link=url_for('timetable.index')
                    )
                    db.session.add(notif)

                    EmailService.send_email(
                        to_email=student.user.email,
                        subject=f"Academic Schedule Update Notice — SkillBasis",
                        template_name='request_edited',
                        context={
                            'user': student.user,
                            'request': req,
                            'admin_response': req.admin_response,
                            'message_intro': f"Please note an administrative update regarding request '{req.title}' for your batch/class."
                        },
                        category=EmailCategory.ACADEMIC,
                        user_id=student.user.id
                    )
                    students_notified_count += 1
                except Exception as st_err:
                    logger.warning(f"Failed to email student {student.id} regarding edited request #{req.id}: {st_err}")

        db.session.commit()
        affected_info['students_notified'] = students_notified_count
        return req, affected_info

    @staticmethod
    def _execute_leave_approval(req):
        curr_d = req.start_date
        while curr_d <= req.end_date:
            rec = TeacherAttendance.query.filter_by(teacher_id=req.teacher_id, date=curr_d).first()
            if rec:
                rec.status = 'leave'
                rec.is_auto_marked = False
            else:
                rec = TeacherAttendance(
                    teacher_id=req.teacher_id,
                    date=curr_d,
                    status='leave',
                    is_auto_marked=False
                )
                db.session.add(rec)
            curr_d += timedelta(days=1)

        # Detect affected classes without deleting them
        affected_timetables = Timetable.query.filter(
            Timetable.teacher_id == req.teacher_id,
            Timetable.is_cancelled == False
        ).all()

        return {'affected_timetables_count': len(affected_timetables)}

    @staticmethod
    def _execute_schedule_change_approval(req):
        tt = req.timetable
        if not tt:
            return {}

        old_date_str = tt.original_date.isoformat() if tt.original_date else tt.day_of_week
        old_time_str = tt.start_time.strftime('%I:%M %p') if tt.start_time else ''

        if req.change_action == 'cancel':
            tt.is_cancelled = True
            tt.cancellation_reason = req.description
        elif req.change_action in ['change_time', 'postpone']:
            if req.proposed_date:
                tt.rescheduled_date = req.proposed_date
                tt.day_of_week = req.proposed_date.strftime('%A')
            if req.proposed_time:
                tt.rescheduled_time = req.proposed_time
                tt.start_time = req.proposed_time

        # Notify enrolled batch students via email & notifications
        students = Student.query.filter_by(batch_id=tt.batch_id, status='active').all()
        new_date_str = tt.rescheduled_date.isoformat() if tt.rescheduled_date else (req.proposed_date.isoformat() if req.proposed_date else 'TBD')
        new_time_str = tt.start_time.strftime('%I:%M %p') if tt.start_time else 'TBD'
        status_label = 'CANCELLED' if tt.is_cancelled else 'RESCHEDULED'

        for student in students:
            try:
                if student.user:
                    notif = Notification(
                        user_id=student.user.id,
                        title=f"Class Schedule Alert: {tt.subject.name if tt.subject else 'Class'} {status_label}",
                        message=f"Class '{tt.subject.name if tt.subject else ''}' ({tt.academic_class.name if tt.academic_class else ''}) has been {status_label.lower()}.",
                        link=url_for('timetable.index')
                    )
                    db.session.add(notif)

                    EmailService.send_email(
                        to_email=student.user.email,
                        subject=f"Class Schedule Alert: {tt.subject.name if tt.subject else 'Class'} {status_label}",
                        template_name='class_schedule_change',
                        context={
                            'user': student.user,
                            'class_name': tt.academic_class.name if tt.academic_class else '',
                            'batch_name': tt.batch.name if tt.batch else '',
                            'subject_name': tt.subject.name if tt.subject else '',
                            'old_schedule': f"{old_date_str} at {old_time_str}",
                            'new_schedule': f"{new_date_str} at {new_time_str}" if not tt.is_cancelled else 'Cancelled',
                            'status_label': status_label,
                            'reason': req.description
                        },
                        category=EmailCategory.ACADEMIC,
                        user_id=student.user.id
                    )
            except Exception as mail_err:
                logger.warning(f"Failed to notify student {student.id} of schedule change: {mail_err}")

        return {'students_notified': len(students)}

    @staticmethod
    def _execute_batch_allocation_approval(req):
        if req.allocation_action == 'remove':
            TeacherAssignment.query.filter_by(
                teacher_id=req.teacher_id,
                class_id=req.target_class_id,
                batch_id=req.target_batch_id,
                subject_id=req.target_subject_id
            ).delete()
        else:
            existing = TeacherAssignment.query.filter_by(
                teacher_id=req.teacher_id,
                class_id=req.target_class_id,
                batch_id=req.target_batch_id,
                subject_id=req.target_subject_id
            ).first()
            if not existing:
                assign = TeacherAssignment(
                    teacher_id=req.teacher_id,
                    class_id=req.target_class_id,
                    batch_id=req.target_batch_id,
                    subject_id=req.target_subject_id
                )
                db.session.add(assign)

        return {'allocation_updated': True}

    @staticmethod
    def _execute_new_class_approval(req):
        day_str = req.proposed_date.strftime('%A') if req.proposed_date else 'Monday'
        start_t = req.proposed_time if req.proposed_time else datetime.strptime('09:00', '%H:%M').time()
        end_t = (datetime.combine(date.today(), start_t) + timedelta(minutes=req.duration_minutes or 60)).time()

        new_tt = Timetable(
            day_of_week=day_str,
            start_time=start_t,
            end_time=end_t,
            class_id=req.target_class_id,
            batch_id=req.target_batch_id,
            subject_id=req.target_subject_id,
            teacher_id=req.teacher_id,
            original_date=req.proposed_date,
            original_time=start_t,
            room_number='Room 101'
        )
        db.session.add(new_tt)

        # Notify batch students
        students = Student.query.filter_by(batch_id=req.target_batch_id, status='active').all()
        for student in students:
            try:
                if student.user:
                    notif = Notification(
                        user_id=student.user.id,
                        title=f"New Class Scheduled: {new_tt.subject.name if new_tt.subject else 'Class'}",
                        message=f"A new class session has been scheduled for {req.proposed_date} at {start_t.strftime('%I:%M %p')}.",
                        link=url_for('timetable.index')
                    )
                    db.session.add(notif)
            except Exception as err:
                logger.warning(f"Failed to create notification for student {student.id}: {err}")

        return {'new_timetable_id': new_tt.id}
