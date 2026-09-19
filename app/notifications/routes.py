import logging
from datetime import datetime
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.communication import Notification
from app.notifications import notifications_bp
from app.services.audit_service import log_action

logger = logging.getLogger(__name__)

@notifications_bp.route('/')
@login_required
def index():
    """
    Full notification page.
    """
    filter_type = request.args.get('filter', 'all').lower().strip()
    query = Notification.query.filter_by(
        user_id=current_user.id,
        is_deleted=False
    )

    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'read':
        query = query.filter_by(is_read=True)

    notifications = query.order_by(Notification.created_at.desc()).all()
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
        is_deleted=False
    ).count()

    return render_template(
        'notifications/index.html',
        notifications=notifications,
        unread_count=unread_count,
        current_filter=filter_type
    )


@notifications_bp.route('/api/list', methods=['GET'])
@login_required
def api_list():
    """
    Returns JSON list of notifications and unread count for topbar dropdown.
    """
    filter_type = request.args.get('filter', 'all').lower().strip()
    query = Notification.query.filter_by(
        user_id=current_user.id,
        is_deleted=False
    )

    if filter_type == 'unread':
        query = query.filter_by(is_read=False)
    elif filter_type == 'read':
        query = query.filter_by(is_read=True)

    notifications = query.order_by(Notification.created_at.desc()).limit(50).all()
    
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
        is_deleted=False
    ).count()

    return jsonify({
        'success': True,
        'unread_count': unread_count,
        'notifications': [n.to_dict() for n in notifications]
    })


@notifications_bp.route('/api/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_read(notif_id):
    """
    Marks single notification as read.
    Reading a notification does NOT delete it.
    """
    notif = Notification.query.filter_by(
        id=notif_id,
        user_id=current_user.id
    ).first()

    if not notif:
        return jsonify({'success': False, 'error': 'Notification not found or access denied.'}), 404

    if not notif.is_read:
        notif.mark_as_read()
        db.session.commit()
        log_action('NOTIFICATION_READ', target_type='Notification', target_id=notif.id, details=f"User marked notification {notif.id} as read.")

    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
        is_deleted=False
    ).count()

    return jsonify({
        'success': True,
        'message': 'Notification marked as read.',
        'unread_count': unread_count,
        'notification': notif.to_dict()
    })


@notifications_bp.route('/api/<int:notif_id>/delete', methods=['POST', 'DELETE'])
@login_required
def delete_notification(notif_id):
    """
    Soft-deletes single notification.
    """
    notif = Notification.query.filter_by(
        id=notif_id,
        user_id=current_user.id
    ).first()

    if not notif:
        return jsonify({'success': False, 'error': 'Notification not found or access denied.'}), 404

    if not notif.is_deleted:
        notif.mark_as_deleted()
        db.session.commit()
        log_action('NOTIFICATION_DELETED', target_type='Notification', target_id=notif.id, details=f"User deleted notification {notif.id}.")

    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
        is_deleted=False
    ).count()

    return jsonify({
        'success': True,
        'message': 'Notification deleted.',
        'unread_count': unread_count
    })


@notifications_bp.route('/api/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    """
    Marks all unread, non-deleted notifications belonging to current_user as read.
    """
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False,
        is_deleted=False
    ).all()

    now = datetime.utcnow()
    count = len(unread_notifications)
    for notif in unread_notifications:
        notif.is_read = True
        notif.read_at = now

    if count > 0:
        db.session.commit()
        log_action('NOTIFICATION_MARK_ALL_READ', target_type='User', target_id=current_user.id, details=f"User marked {count} notifications as read.")

    return jsonify({
        'success': True,
        'message': f'Marked {count} notifications as read.',
        'unread_count': 0
    })


@notifications_bp.route('/api/clear-all', methods=['POST'])
@login_required
def clear_all():
    """
    Soft-deletes all non-deleted notifications belonging to current_user.
    """
    active_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_deleted=False
    ).all()

    now = datetime.utcnow()
    count = len(active_notifications)
    for notif in active_notifications:
        notif.is_deleted = True
        notif.deleted_at = now

    if count > 0:
        db.session.commit()
        log_action('NOTIFICATION_CLEAR_ALL', target_type='User', target_id=current_user.id, details=f"User cleared all {count} notifications.")

    return jsonify({
        'success': True,
        'message': f'Cleared {count} notifications.',
        'unread_count': 0
    })
