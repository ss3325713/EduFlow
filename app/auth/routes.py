from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.extensions import db
from app.models import User, Role
from app.services.audit_service import log_action

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        login_identifier = request.form.get('login_identifier', '').strip()
        password = request.form.get('password', '')
        remember = True if request.form.get('remember') else False

        # Support login by username or email
        user = User.query.filter(
            (User.username == login_identifier) | (User.email == login_identifier)
        ).first()

        if not user or not user.check_password(password):
            flash('Invalid username/email or password. Please try again.', 'danger')
            return render_template('auth/login.html', login_identifier=login_identifier)

        if not user.is_active:
            flash('Your account has been deactivated. Please contact the administrator.', 'warning')
            return render_template('auth/login.html', login_identifier=login_identifier)

        login_user(user, remember=remember)
        log_action('USER_LOGIN', target_type='User', target_id=user.id, details=f"User {user.username} logged in successfully.")

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    log_action('USER_LOGOUT', target_type='User', target_id=current_user.id)
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        first_name = request.form.get('first_name', '').strip()
        last_name = request.form.get('last_name', '').strip()
        email = request.form.get('email', '').strip()
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        # Check if email is already taken by another user
        existing_user = User.query.filter(User.email == email, User.id != current_user.id).first()
        if existing_user:
            flash('This email address is already in use by another account.', 'danger')
            return render_template('auth/profile.html')

        current_user.first_name = first_name
        current_user.last_name = last_name
        current_user.email = email

        if new_password:
            if len(new_password) < 6:
                flash('Password must be at least 6 characters long.', 'danger')
                return render_template('auth/profile.html')
            if new_password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return render_template('auth/profile.html')
            current_user.set_password(new_password)
            flash('Password updated successfully.', 'success')

        db.session.commit()
        log_action('PROFILE_UPDATED', target_type='User', target_id=current_user.id)
        flash('Profile details updated successfully.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')
