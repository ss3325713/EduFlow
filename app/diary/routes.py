import logging
import calendar
from datetime import datetime, date, timedelta
from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.extensions import db
from app.models.diary import DiaryEntry
from app.diary import diary_bp
from app.diary.encryption import encrypt_diary_content, decrypt_diary_content

logger = logging.getLogger(__name__)

@diary_bp.route('/')
@diary_bp.route('/index')
@login_required
def index():
    """
    Renders main Personal Digital Diary interface.
    Supports four independent view modes: 'day', 'week', 'month', 'year'.
    """
    view_mode = request.args.get('view', 'day').lower().strip()
    if view_mode not in ['day', 'week', 'month', 'year']:
        view_mode = 'day'
        
    date_param = request.args.get('date', '').strip()
    today_str = date.today().isoformat()
    selected_date = date_param if date_param else today_str

    return render_template(
        'diary/index.html',
        initial_view=view_mode,
        initial_date=selected_date,
        today_date=today_str
    )


@diary_bp.route('/api/entries', methods=['GET'])
@login_required
def get_entries_summary():
    """
    Summary API: Returns dates with diary entries for current_user within specified scope.
    PRIVACY GUARANTEE: Plaintext content is NEVER returned in summary list.
    """
    start_str = request.args.get('start_date', '').strip()
    end_str = request.args.get('end_date', '').strip()
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    query = DiaryEntry.query.filter(DiaryEntry.owner_user_id == current_user.id)

    if start_str and end_str:
        try:
            s_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            e_date = datetime.strptime(end_str, '%Y-%m-%d').date()
            query = query.filter(DiaryEntry.diary_date >= s_date, DiaryEntry.diary_date <= e_date)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid date format for range.'}), 400
    elif year and month:
        _, last_day = calendar.monthrange(year, month)
        query = query.filter(
            DiaryEntry.diary_date >= date(year, month, 1),
            DiaryEntry.diary_date <= date(year, month, last_day)
        )
    elif year:
        query = query.filter(
            DiaryEntry.diary_date >= date(year, 1, 1),
            DiaryEntry.diary_date <= date(year, 12, 31)
        )

    entries = query.order_by(DiaryEntry.diary_date.asc()).all()
    summary = [{
        'date': e.diary_date.isoformat(),
        'has_entry': True
    } for e in entries]

    return jsonify({
        'success': True,
        'count': len(summary),
        'entries': summary
    })


@diary_bp.route('/api/entry/<date_str>', methods=['GET'])
@login_required
def get_entry_by_date(date_str):
    """
    Retrieves and decrypts diary entry for current_user for specified date.
    Strictly isolated: Users cannot access entries belonging to other users.
    """
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    entry = DiaryEntry.query.filter_by(
        owner_user_id=current_user.id,
        diary_date=target_date
    ).first()

    if not entry:
        return jsonify({
            'success': True,
            'has_entry': False,
            'diary_date': date_str,
            'entry': None
        })

    decrypted_text = decrypt_diary_content(entry.encrypted_content, current_user.id)
    return jsonify({
        'success': True,
        'has_entry': True,
        'diary_date': date_str,
        'entry': entry.to_dict(decrypted_text=decrypted_text)
    })


@diary_bp.route('/api/entry', methods=['POST'])
@diary_bp.route('/api/entry/<date_str>', methods=['POST', 'PUT'])
@login_required
def save_entry(date_str=None):
    """
    Creates or updates single diary entry for current_user for target date.
    Strictly enforces server-side owner_user_id = current_user.id.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    
    target_date_str = date_str or data.get('diary_date', '').strip()
    content = data.get('content', '').strip()

    if not target_date_str:
        return jsonify({'success': False, 'error': 'Diary date is required.'}), 400

    try:
        target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    if not content:
        return jsonify({'success': False, 'error': 'Diary entry content cannot be empty.'}), 400

    try:
        encrypted_text = encrypt_diary_content(content, current_user.id)
        
        entry = DiaryEntry.query.filter_by(
            owner_user_id=current_user.id,
            diary_date=target_date
        ).first()

        if entry:
            entry.encrypted_content = encrypted_text
            entry.updated_at = datetime.utcnow()
            message = "Diary entry updated successfully."
        else:
            entry = DiaryEntry(
                owner_user_id=current_user.id,
                diary_date=target_date,
                encrypted_content=encrypted_text,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.session.add(entry)
            message = "Diary entry saved successfully."

        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': message,
            'entry': entry.to_dict(decrypted_text=content)
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving diary entry for user {current_user.id} on date {target_date_str}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to save diary entry due to a server error. Please try again.'}), 500


@diary_bp.route('/api/entry/<date_str>', methods=['DELETE'])
@login_required
def delete_entry(date_str):
    """
    Deletes diary entry for current_user on target date.
    """
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'success': False, 'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    entry = DiaryEntry.query.filter_by(
        owner_user_id=current_user.id,
        diary_date=target_date
    ).first()

    if not entry:
        return jsonify({'success': False, 'error': 'No diary entry found for this date.'}), 404

    try:
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Diary entry deleted successfully.'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting diary entry for user {current_user.id} on date {date_str}: {e}", exc_info=True)
        return jsonify({'success': False, 'error': 'Failed to delete diary entry.'}), 500
