from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import auth_bp
from app.extensions import db
from app.models import User, Role, EmailPreference, EmailCategory
from app.services.audit_service import log_action
from app.services.email_service import EmailService

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    active_tab = request.form.get('login_type', 'portal')

    if request.method == 'POST':
        login_type = request.form.get('login_type', 'portal')
        remember = True if request.form.get('remember') else False
        password = request.form.get('password', '')

        # ----------------------------------------------------
        # 1. Super Admin Authentication (Requires Email + Password)
        # ----------------------------------------------------
        if login_type == 'super_admin':
            email_input = request.form.get('email', '').strip().lower()

            if not email_input:
                flash('Please enter your Super Admin email address.', 'danger')
                return render_template('auth/login.html', active_tab='super_admin')

            user = User.query.filter_by(email=email_input, role=Role.SUPER_ADMIN).first()

            if not user or not user.check_password(password):
                flash('Invalid Super Admin email address or password.', 'danger')
                return render_template('auth/login.html', active_tab='super_admin', email=email_input)

            if not user.is_active:
                flash('Super Admin account has been deactivated. Please contact support.', 'warning')
                return render_template('auth/login.html', active_tab='super_admin')

            login_user(user, remember=remember)
            log_action('SUPER_ADMIN_LOGIN', target_type='User', target_id=user.id, details=f"Super Admin ({user.email}) logged in successfully.")

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))

        # ----------------------------------------------------
        # 2. Portal Login (Students, Teachers, Parents, Staff)
        # ----------------------------------------------------
        else:
            login_identifier = request.form.get('login_identifier', '').strip()

            # Reject username "admin" or Super Admin email attempts in standard portal login
            super_admin_match = User.query.filter(
                (User.username == login_identifier) | (User.email == login_identifier)
            ).filter(User.role == Role.SUPER_ADMIN).first()

            if super_admin_match and login_identifier.lower() == super_admin_match.username.lower():
                flash('Super Admin authentication requires logging in with your Email Address on the Super Admin tab.', 'warning')
                return render_template('auth/login.html', active_tab='super_admin', email=super_admin_match.email)

            # Query user for non-super-admin roles or email match
            user = User.query.filter(
                (User.username == login_identifier) | (User.email == login_identifier)
            ).first()

            # If user is Super Admin but entered valid email in general tab, redirect to Super Admin auth
            if user and user.is_super_admin():
                if user.check_password(password):
                    login_user(user, remember=remember)
                    log_action('SUPER_ADMIN_LOGIN', target_type='User', target_id=user.id, details=f"Super Admin ({user.email}) logged in via email.")
                    next_page = request.args.get('next')
                    if next_page and next_page.startswith('/'):
                        return redirect(next_page)
                    return redirect(url_for('dashboard.index'))

            if not user or not user.check_password(password):
                flash('Invalid username/email or password. Please try again.', 'danger')
                return render_template('auth/login.html', active_tab='portal', login_identifier=login_identifier)

            if not user.is_active:
                flash('Your account has been deactivated. Please contact the administrator.', 'warning')
                return render_template('auth/login.html', active_tab='portal', login_identifier=login_identifier)

            if not user.is_verified:
                flash('Your account email address is pending verification. Please check your inbox or request a new verification email.', 'info')

            login_user(user, remember=remember)
            log_action('USER_LOGIN', target_type='User', target_id=user.id, details=f"User {user.username} logged in successfully.")

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)

            return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html', active_tab=active_tab)

@auth_bp.route('/logout')
@login_required
def logout():
    log_action('USER_LOGOUT', target_type='User', target_id=current_user.id)
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    user = User.query.filter(User.verification_token_hash.isnot(None)).all()
    verified_user = None
    for u in user:
        if u.verify_email_token(token):
            verified_user = u
            db.session.commit()
            break

    if verified_user:
        log_action('EMAIL_VERIFIED', target_type='User', target_id=verified_user.id, details=f"Email address verified for user {verified_user.username}")
        # Send confirmation email
        base_url = current_app.config.get('APP_BASE_URL', 'http://localhost:5000')
        EmailService.send_email(
            to_email=verified_user.email,
            subject='Email Verified Successfully — EduFlow',
            template_name='verification_success',
            context={'user': verified_user, 'login_url': f"{base_url}{url_for('auth.login')}"},
            category=EmailCategory.AUTHENTICATION,
            user_id=verified_user.id
        )
        return render_template('auth/verify_email.html', success=True, user=verified_user)
    else:
        log_action('EMAIL_VERIFICATION_FAILED', details="Invalid or expired email verification token attempt")
        return render_template('auth/verify_email.html', success=False)

@auth_bp.route('/resend-verification', methods=['GET', 'POST'])
def resend_verification():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        if user and not user.is_verified:
            token = user.generate_verification_token()
            db.session.commit()
            base_url = current_app.config.get('APP_BASE_URL', 'http://localhost:5000')
            verify_url = f"{base_url}{url_for('auth.verify_email', token=token)}"

            EmailService.send_email(
                to_email=user.email,
                subject='Verify Your EduFlow Email Address',
                template_name='verification_email',
                context={'user': user, 'verify_url': verify_url},
                category=EmailCategory.AUTHENTICATION,
                user_id=user.id
            )
            log_action('VERIFICATION_EMAIL_RESENT', target_type='User', target_id=user.id)

        flash('If an unverified account exists for that email, a new verification link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/resend_verification.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()

        if user:
            token = user.generate_password_reset_token()
            db.session.commit()
            base_url = current_app.config.get('APP_BASE_URL', 'http://localhost:5000')
            reset_url = f"{base_url}{url_for('auth.reset_password', token=token)}"

            EmailService.send_email(
                to_email=user.email,
                subject='Reset Your EduFlow Account Password',
                template_name='password_reset',
                context={'user': user, 'reset_url': reset_url},
                category=EmailCategory.SECURITY,
                user_id=user.id
            )
            log_action('PASSWORD_RESET_REQUESTED', target_type='User', target_id=user.id)

        flash('If an account exists for that email, password reset instructions have been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    users = User.query.filter(User.password_reset_token_hash.isnot(None)).all()
    target_user = None
    for u in users:
        if u.verify_password_reset_token(token):
            target_user = u
            break

    if not target_user:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        new_password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        target_user.set_password(new_password)
        target_user.clear_password_reset_token()
        db.session.commit()

        log_action('PASSWORD_RESET_COMPLETED', target_type='User', target_id=target_user.id)

        # Send security notification
        EmailService.send_email(
            to_email=target_user.email,
            subject='EduFlow Account Password Changed',
            template_name='password_changed',
            context={'user': target_user, 'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')},
            category=EmailCategory.SECURITY,
            user_id=target_user.id
        )

        flash('Your password has been reset successfully. Please log in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)

@auth_bp.route('/email-preferences', methods=['GET', 'POST'])
@login_required
def email_preferences():
    if request.method == 'POST':
        for cat_code, label in EmailCategory.OPTIONAL_CATEGORIES:
            enabled = True if request.form.get(f'cat_{cat_code}') else False
            EmailPreference.set_category_preference(current_user.id, cat_code, enabled)

        flash('Email notification preferences saved.', 'success')
        log_action('EMAIL_PREFERENCES_UPDATED', target_type='User', target_id=current_user.id)
        return redirect(url_for('auth.email_preferences'))

    user_prefs = {pref.category: pref.enabled for pref in current_user.email_preferences.all()}
    categories = []
    for cat_code, label in EmailCategory.OPTIONAL_CATEGORIES:
        categories.append({
            'code': cat_code,
            'label': label,
            'enabled': user_prefs.get(cat_code, True)
        })

    return render_template('auth/email_preferences.html', categories=categories)

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

            # Send password change alert
            EmailService.send_email(
                to_email=current_user.email,
                subject='EduFlow Account Password Changed',
                template_name='password_changed',
                context={'user': current_user, 'timestamp': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')},
                category=EmailCategory.SECURITY,
                user_id=current_user.id
            )
            flash('Password updated successfully.', 'success')

        db.session.commit()
        log_action('PROFILE_UPDATED', target_type='User', target_id=current_user.id)
        flash('Profile details updated successfully.', 'success')
        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html')
