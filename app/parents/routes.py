from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.parents import parents_bp
from app.extensions import db
from app.models import Parent, User, Role, Student, StudentParent
from app.utils.decorators import admin_required, super_admin_required
from app.services.audit_service import log_action

@parents_bp.route('/')
@login_required
@admin_required
def index():
    parents = Parent.query.join(User).order_by(User.first_name.asc()).all()
    students = Student.query.join(User).order_by(User.first_name.asc()).all()
    return render_template('parents/index.html', parents=parents, students=students)

@parents_bp.route('/add', methods=['GET', 'POST'])
@login_required
@admin_required
def add():
    students = Student.query.join(User).order_by(User.first_name.asc()).all()

    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', 'Parent@123')
        mobile = request.form.get('mobile', '').strip()
        occupation = request.form.get('occupation', '').strip()
        address = request.form.get('address', '').strip()
        student_id = request.form.get('student_id', type=int)
        relationship = request.form.get('relationship', 'parent')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.', 'danger')
            return render_template('parents/form.html', students=students)

        if User.query.filter_by(email=email).first():
            flash('Email address already exists.', 'danger')
            return render_template('parents/form.html', students=students)

        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=Role.PARENT,
            is_active=True
        )
        user.set_password(password)
        db.session.add(user)
        db.session.flush()

        parent = Parent(
            user_id=user.id,
            mobile=mobile,
            occupation=occupation,
            address=address
        )
        db.session.add(parent)
        db.session.flush()

        if student_id:
            link = StudentParent(
                student_id=student_id,
                parent_id=parent.id,
                relationship=relationship
            )
            db.session.add(link)

        db.session.commit()
        log_action('PARENT_CREATED', target_type='Parent', target_id=parent.id, details=f"Created parent account for {parent.full_name}")
        flash(f'Parent account for "{parent.full_name}" created successfully.', 'success')
        return redirect(url_for('parents.index'))

    return render_template('parents/form.html', students=students)

@parents_bp.route('/link', methods=['POST'])
@login_required
@admin_required
def link_student():
    parent_id = request.form.get('parent_id', type=int)
    student_id = request.form.get('student_id', type=int)
    relationship = request.form.get('relationship', 'parent')

    if parent_id and student_id:
        existing = StudentParent.query.filter_by(parent_id=parent_id, student_id=student_id).first()
        if not existing:
            link = StudentParent(student_id=student_id, parent_id=parent_id, relationship=relationship)
            db.session.add(link)
            db.session.commit()
            flash('Child linked to parent account successfully.', 'success')
        else:
            flash('This child is already linked to the parent.', 'info')

    return redirect(url_for('parents.index'))

@parents_bp.route('/delink/<int:parent_id>/<int:student_id>', methods=['POST'])
@login_required
@admin_required
def delink_student(parent_id, student_id):
    link = StudentParent.query.filter_by(parent_id=parent_id, student_id=student_id).first_or_404()
    student_name = link.student.full_name
    parent_name = link.parent.full_name
    db.session.delete(link)
    db.session.commit()
    log_action('PARENT_DELINKED_CHILD', target_type='StudentParent', target_id=link.id, details=f"Delinked student '{student_name}' from parent '{parent_name}'")
    flash(f'Student "{student_name}" delinked from parent "{parent_name}".', 'info')
    return redirect(url_for('parents.index'))

@parents_bp.route('/<int:parent_id>/disable', methods=['POST'])
@login_required
@super_admin_required
def disable(parent_id):
    parent = Parent.query.get_or_404(parent_id)
    parent.user.is_active = False
    db.session.commit()
    log_action('PARENT_DISABLED', target_type='Parent', target_id=parent.id, details=f"Disabled login for parent '{parent.full_name}'")
    flash(f'Parent account for "{parent.full_name}" disabled.', 'info')
    return redirect(url_for('parents.index'))

@parents_bp.route('/<int:parent_id>/enable', methods=['POST'])
@login_required
@super_admin_required
def enable(parent_id):
    parent = Parent.query.get_or_404(parent_id)
    parent.user.is_active = True
    db.session.commit()
    log_action('PARENT_ENABLED', target_type='Parent', target_id=parent.id, details=f"Re-enabled login for parent '{parent.full_name}'")
    flash(f'Parent account for "{parent.full_name}" re-enabled.', 'success')
    return redirect(url_for('parents.index'))

@parents_bp.route('/<int:parent_id>/delete', methods=['POST'])
@login_required
@super_admin_required
def delete(parent_id):
    parent = Parent.query.get_or_404(parent_id)
    parent_name = parent.full_name
    user = parent.user

    if user.is_active:
        flash(f'Cannot permanently delete active parent "{parent_name}". Please disable the account first.', 'danger')
        return redirect(url_for('parents.index'))

    db.session.delete(user)
    db.session.commit()

    log_action('PARENT_PERMANENTLY_DELETED', target_type='Parent', target_id=parent_id, details=f"Super Admin permanently deleted parent account '{parent_name}'")
    flash(f'Parent account for "{parent_name}" permanently purged from database.', 'warning')
    return redirect(url_for('parents.index'))
