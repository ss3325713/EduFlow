from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.subjects import subjects_bp
from app.extensions import db
from app.models import Subject, Class
from app.utils.decorators import admin_required
from app.services.audit_service import log_action

@subjects_bp.route('/')
@login_required
def index():
    subjects = Subject.query.order_by(Subject.name.asc()).all()
    classes = Class.query.order_by(Class.name).all()
    return render_template('subjects/index.html', subjects=subjects, classes=classes)

@subjects_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    classes = Class.query.order_by(Class.name).all()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        class_id = request.form.get('class_id', type=int)
        description = request.form.get('description', '').strip()

        subject = Subject(
            name=name,
            code=code,
            class_id=class_id,
            description=description
        )
        db.session.add(subject)
        db.session.commit()

        log_action('SUBJECT_CREATED', target_type='Subject', target_id=subject.id, details=f"Created subject '{subject.name}' for class {class_id}")
        flash(f'Subject "{subject.name}" added successfully.', 'success')
        return redirect(url_for('subjects.index'))

    return render_template('subjects/form.html', classes=classes)
