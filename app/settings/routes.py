from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.settings import settings_bp
from app.extensions import db
from app.models import InstituteSettings
from app.utils.decorators import super_admin_required
from app.services.audit_service import log_action

@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
@super_admin_required
def index():
    settings = InstituteSettings.get_settings()

    if request.method == 'POST':
        settings.name = request.form.get('name', 'EduFlow Academy').strip()
        settings.tagline = request.form.get('tagline', '').strip()
        settings.phone = request.form.get('phone', '').strip()
        settings.email = request.form.get('email', '').strip()
        settings.address = request.form.get('address', '').strip()
        settings.academic_session = request.form.get('academic_session', '').strip()
        settings.country = request.form.get('country', 'United States').strip()
        settings.currency = request.form.get('currency', '$').strip()
        settings.timezone = request.form.get('timezone', 'UTC').strip()

        db.session.commit()
        log_action('INSTITUTE_SETTINGS_UPDATED', target_type='InstituteSettings', target_id=settings.id, details=f"Updated institute settings. Name: {settings.name}")
        flash('Institute settings updated successfully.', 'success')
        return redirect(url_for('settings.index'))

    return render_template('settings/index.html', settings=settings)
