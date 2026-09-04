from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.classes import classes_bp
from app.extensions import db
from app.models import Class
from app.utils.decorators import admin_required
from app.services.audit_service import log_action

@classes_bp.route('/')
@login_required
def index():
    classes = Class.query.order_by(Class.name.asc()).all()
    return render_template('classes/index.html', classes=classes)

@classes_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        description = request.form.get('description', '').strip()

        if Class.query.filter_by(name=name).first():
            flash('Class with this name already exists.', 'danger')
            return render_template('classes/form.html')

        if Class.query.filter_by(code=code).first():
            flash('Class code must be unique.', 'danger')
            return render_template('classes/form.html')

        cls = Class(name=name, code=code, description=description)
        db.session.add(cls)
        db.session.commit()

        log_action('CLASS_CREATED', target_type='Class', target_id=cls.id, details=f"Created class '{cls.name}'")
        flash(f'Class "{cls.name}" created successfully.', 'success')
        return redirect(url_for('classes.index'))

    return render_template('classes/form.html')

@classes_bp.route('/<int:class_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit(class_id):
    cls = Class.query.get_or_404(class_id)
    if request.method == 'POST':
        cls.name = request.form.get('name', '').strip()
        cls.code = request.form.get('code', '').strip()
        cls.description = request.form.get('description', '').strip()

        db.session.commit()
        log_action('CLASS_UPDATED', target_type='Class', target_id=cls.id, details=f"Updated class '{cls.name}'")
        flash(f'Class "{cls.name}" updated successfully.', 'success')
        return redirect(url_for('classes.index'))

    return render_template('classes/form.html', cls=cls)
