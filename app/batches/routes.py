from datetime import datetime
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.batches import batches_bp
from app.extensions import db
from app.models import Batch, Class, Student, TeacherAssignment
from app.utils.decorators import admin_required, teacher_required
from app.services.audit_service import log_action

@batches_bp.route('/')
@login_required
@teacher_required
def index():
    batches = Batch.query.order_by(Batch.name.asc()).all()
    classes = Class.query.order_by(Class.name).all()
    return render_template('batches/index.html', batches=batches, classes=classes)

@batches_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    classes = Class.query.order_by(Class.name).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        class_id = request.form.get('class_id', type=int)
        max_capacity = request.form.get('max_capacity', type=int, default=30)
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        schedule_description = request.form.get('schedule_description', '').strip()

        if Batch.query.filter_by(code=code).first():
            flash('Batch code must be unique.', 'danger')
            return render_template('batches/form.html', classes=classes)

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

        batch = Batch(
            name=name,
            code=code,
            class_id=class_id,
            max_capacity=max_capacity,
            start_date=start_date,
            end_date=end_date,
            schedule_description=schedule_description,
            status='active'
        )
        db.session.add(batch)
        db.session.commit()

        log_action('BATCH_CREATED', target_type='Batch', target_id=batch.id, details=f"Created batch '{batch.name}' (Cap: {max_capacity})")
        flash(f'Batch "{batch.name}" created successfully.', 'success')
        return redirect(url_for('batches.index'))

    return render_template('batches/form.html', classes=classes)

@batches_bp.route('/<int:batch_id>')
@login_required
@teacher_required
def view(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    students = Student.query.filter_by(batch_id=batch.id, status='active').all()
    assignments = TeacherAssignment.query.filter_by(batch_id=batch.id).all()
    return render_template('batches/view.html', batch=batch, students=students, assignments=assignments)

@batches_bp.route('/<int:batch_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(batch_id):
    batch = Batch.query.get_or_404(batch_id)
    classes = Class.query.order_by(Class.name).all()

    if request.method == 'POST':
        batch.name = request.form.get('name', '').strip()
        batch.code = request.form.get('code', '').strip()
        batch.class_id = request.form.get('class_id', type=int)
        batch.max_capacity = request.form.get('max_capacity', type=int, default=30)
        batch.schedule_description = request.form.get('schedule_description', '').strip()
        batch.status = request.form.get('status', 'active')

        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        batch.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        batch.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

        db.session.commit()
        log_action('BATCH_UPDATED', target_type='Batch', target_id=batch.id, details=f"Updated batch '{batch.name}'")
        flash(f'Batch "{batch.name}" updated successfully.', 'success')
        return redirect(url_for('batches.view', batch_id=batch.id))

    return render_template('batches/form.html', batch=batch, classes=classes)
