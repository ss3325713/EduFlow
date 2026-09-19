from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.requests import requests_bp
from app.models import TeacherRequest, Teacher, User, Class, Batch, Subject
from app.utils.decorators import admin_required
from app.services.request_service import RequestService

@requests_bp.route('/admin', methods=['GET'], endpoint='admin_center')
@requests_bp.route('/admin/center', methods=['GET'], endpoint='admin_index')
@login_required
@admin_required
def admin_index():
    category = request.args.get('category', '').strip()
    teacher_id = request.args.get('teacher_id', type=int)
    status = request.args.get('status', '').strip()
    search = request.args.get('search', '').strip()

    query = TeacherRequest.query.join(Teacher, TeacherRequest.teacher_id == Teacher.id).join(User, Teacher.user_id == User.id)

    if category:
        query = query.filter(TeacherRequest.request_type == category)
    if teacher_id:
        query = query.filter(TeacherRequest.teacher_id == teacher_id)
    if status:
        query = query.filter(TeacherRequest.status == status)
    if search:
        query = query.filter(
            (TeacherRequest.title.ilike(f'%{search}%')) |
            (TeacherRequest.description.ilike(f'%{search}%')) |
            (User.first_name.ilike(f'%{search}%')) |
            (User.last_name.ilike(f'%{search}%'))
        )

    requests_list = query.order_by(TeacherRequest.created_at.desc()).all()
    pending_requests = [r for r in requests_list if r.status == 'pending']
    approved_requests = [r for r in requests_list if r.status == 'approved']
    rejected_requests = [r for r in requests_list if r.status == 'rejected']

    teachers = Teacher.query.join(User).order_by(User.first_name.asc()).all()
    classes = Class.query.order_by(Class.name.asc()).all()
    batches = Batch.query.order_by(Batch.name.asc()).all()
    subjects = Subject.query.order_by(Subject.name.asc()).all()

    # Metrics summary for cards
    pending_count = len(pending_requests)
    leave_pending = sum(1 for r in pending_requests if r.request_type == 'leave')
    schedule_pending = sum(1 for r in pending_requests if r.request_type == 'schedule_change')
    allocation_pending = sum(1 for r in pending_requests if r.request_type == 'batch_allocation')
    new_class_pending = sum(1 for r in pending_requests if r.request_type == 'schedule_new_class')

    return render_template('requests/admin_center.html',
                           requests_list=requests_list,
                           pending_requests=pending_requests,
                           approved_requests=approved_requests,
                           rejected_requests=rejected_requests,
                           all_requests=requests_list,
                           teachers=teachers,
                           classes=classes,
                           batches=batches,
                           subjects=subjects,
                           category=category,
                           teacher_id=teacher_id,
                           status=status,
                           search=search,
                           pending_count=pending_count,
                           leave_pending=leave_pending,
                           schedule_pending=schedule_pending,
                           allocation_pending=allocation_pending,
                           new_class_pending=new_class_pending)

@requests_bp.route('/admin/<int:request_id>/process', methods=['POST'])
@requests_bp.route('/process/<int:request_id>', methods=['POST'])
@login_required
@admin_required
def process_request(request_id):
    status = request.form.get('status', '').strip().lower()
    admin_response = request.form.get('admin_response', '').strip()

    try:
        req, affected_info = RequestService.process_request(
            request_id=request_id,
            status=status,
            admin_user=current_user,
            admin_response=admin_response
        )

        msg = f"Request #{request_id} has been successfully updated to '{status.title()}'."
        if affected_info.get('students_notified'):
            msg += f" ({affected_info['students_notified']} students notified via email)."
        if affected_info.get('affected_timetables_count'):
            msg += f" Note: {affected_info['affected_timetables_count']} class schedule(s) overlap with this leave period."

        flash(msg, 'success')
    except Exception as err:
        flash(f"Error processing request: {str(err)}", 'danger')

    return redirect(url_for('requests.admin_index'))

@requests_bp.route('/admin/<int:request_id>/edit', methods=['POST'])
@requests_bp.route('/edit/<int:request_id>', methods=['POST'])
@login_required
@admin_required
def edit_request(request_id):
    try:
        req, affected_info = RequestService.edit_approved_request(
            request_id=request_id,
            form_data=request.form,
            admin_user=current_user
        )

        msg = f"Request #{request_id} has been successfully modified."
        if affected_info.get('students_notified'):
            msg += f" ({affected_info['students_notified']} student(s) and assigned teacher notified via email)."

        flash(msg, 'success')
    except Exception as err:
        flash(f"Error editing request #{request_id}: {str(err)}", 'danger')

    return redirect(url_for('requests.admin_index'))

