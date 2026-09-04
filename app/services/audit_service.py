from flask import request
from flask_login import current_user
from app.extensions import db
from app.models.system import AuditLog

def log_action(action, target_type=None, target_id=None, details=None, user_id=None):
    try:
        ip_address = request.remote_addr if request else None
        acting_user_id = user_id or (current_user.id if (current_user and current_user.is_authenticated) else None)
        
        log_entry = AuditLog(
            user_id=acting_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=ip_address
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Logging should never crash the primary request
        print(f"Audit log failed: {e}")
