from functools import wraps
from flask import flash, redirect, url_for, request, jsonify, abort
from flask_login import current_user
from app.models.user import Role

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Authentication required'}), 401
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))

            if current_user.role not in roles and not current_user.is_super_admin():
                if request.is_json or request.path.startswith('/api/'):
                    return jsonify({'error': 'Permission denied'}), 403
                flash('You do not have permission to access this resource.', 'danger')
                return redirect(url_for('dashboard.index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def super_admin_required(f):
    return role_required(Role.SUPER_ADMIN)(f)

def admin_required(f):
    return role_required(Role.SUPER_ADMIN, Role.ADMIN)(f)

def teacher_required(f):
    return role_required(Role.SUPER_ADMIN, Role.ADMIN, Role.TEACHER)(f)

def student_required(f):
    return role_required(Role.STUDENT)(f)

def parent_required(f):
    return role_required(Role.PARENT)(f)
