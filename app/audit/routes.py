from flask import render_template, request
from flask_login import login_required
from app.audit import audit_bp
from app.models import AuditLog
from app.utils.decorators import super_admin_required

@audit_bp.route('/')
@login_required
@super_admin_required
def index():
    action_filter = request.args.get('action', '').strip()
    query = AuditLog.query

    if action_filter:
        query = query.filter(AuditLog.action.ilike(f'%{action_filter}%'))

    logs = query.order_by(AuditLog.timestamp.desc()).limit(100).all()
    return render_template('audit/index.html', logs=logs, action_filter=action_filter)
