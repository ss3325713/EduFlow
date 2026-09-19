import os
from pathlib import Path
from flask import Flask, render_template, redirect, url_for
from flask_login import current_user

from config import config_by_name
from app.extensions import db, login_manager, migrate, csrf
from app.models import User, Role, InstituteSettings

def create_app(config_name='development'):
    app = Flask(__name__, 
                template_folder=str(Path(__file__).resolve().parent.parent / 'templates'),
                static_folder=str(Path(__file__).resolve().parent.parent / 'static'))
    
    config_cls = config_by_name.get(config_name, config_by_name['default'])
    app.config.from_object(config_cls)

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Automatic self-healing database schema initialization
    with app.app_context():
        try:
            db.create_all()
            with db.engine.connect() as conn:
                inspector = db.inspect(db.engine)
                tables = inspector.get_table_names()
                is_pg = 'postgres' in db.engine.name.lower()
                dt_type = "TIMESTAMP" if is_pg else "DATETIME"
                bool_true = "TRUE" if is_pg else "1"
                bool_false = "FALSE" if is_pg else "0"

                if 'users' in tables:
                    existing_cols = [c['name'] for c in inspector.get_columns('users')]
                    if 'is_verified' not in existing_cols:
                        conn.execute(db.text(f"ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT {bool_true}"))
                    if 'verification_token_hash' not in existing_cols:
                        conn.execute(db.text("ALTER TABLE users ADD COLUMN verification_token_hash VARCHAR(128)"))
                    if 'verification_sent_at' not in existing_cols:
                        conn.execute(db.text(f"ALTER TABLE users ADD COLUMN verification_sent_at {dt_type}"))
                    if 'password_reset_token_hash' not in existing_cols:
                        conn.execute(db.text("ALTER TABLE users ADD COLUMN password_reset_token_hash VARCHAR(128)"))
                    if 'password_reset_expires_at' not in existing_cols:
                        conn.execute(db.text(f"ALTER TABLE users ADD COLUMN password_reset_expires_at {dt_type}"))
                if 'notifications' in tables:
                    notif_cols = [c['name'] for c in inspector.get_columns('notifications')]
                    if 'read_at' not in notif_cols:
                        conn.execute(db.text(f"ALTER TABLE notifications ADD COLUMN read_at {dt_type}"))
                    if 'is_deleted' not in notif_cols:
                        conn.execute(db.text(f"ALTER TABLE notifications ADD COLUMN is_deleted BOOLEAN DEFAULT {bool_false}"))
                    if 'deleted_at' not in notif_cols:
                        conn.execute(db.text(f"ALTER TABLE notifications ADD COLUMN deleted_at {dt_type}"))
                conn.commit()
        except Exception as err:
            app.logger.warning(f"Auto database schema migration notice: {err}")

    @login_manager.user_loader
    def load_user(user_id):
        if not user_id:
            return None
        try:
            clean_id = str(user_id).split('|')[0]
            return User.query.get(int(clean_id))
        except (ValueError, TypeError):
            return None


    # Global context processors for templates
    @app.context_processor
    def inject_global_vars():
        try:
            settings = InstituteSettings.get_settings()
        except Exception:
            settings = None

        unread_notifications_count = 0
        if current_user and current_user.is_authenticated:
            try:
                from app.models.communication import Notification
                unread_notifications_count = Notification.query.filter_by(
                    user_id=current_user.id,
                    is_read=False,
                    is_deleted=False
                ).count()
            except Exception:
                unread_notifications_count = 0

        return {
            'institute_settings': settings,
            'Role': Role,
            'unread_notifications_count': unread_notifications_count
        }

    # Template filter for localized currency formatting
    @app.template_filter('currency')
    def currency_filter(amount):
        try:
            settings = InstituteSettings.get_settings()
            sym = settings.currency if settings and settings.currency else '$'
            val = float(amount or 0.0)
            return f"{sym}{val:,.2f}"
        except Exception:
            return f"${amount:,.2f}"

    # Root redirect
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for('dashboard.index'))
        return redirect(url_for('auth.login'))

    # Custom Error Handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500

    # Register Blueprints
    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.students import students_bp
    from app.teachers import teachers_bp
    from app.parents import parents_bp
    from app.classes import classes_bp
    from app.batches import batches_bp
    from app.subjects import subjects_bp
    from app.fees import fees_bp
    from app.attendance import attendance_bp
    from app.timetable import timetable_bp
    from app.exams import exams_bp
    from app.assignments import assignments_bp
    from app.materials import materials_bp
    from app.announcements import announcements_bp
    from app.admissions import admissions_bp
    from app.reports import reports_bp
    from app.settings import settings_bp
    from app.audit import audit_bp
    from app.diary import diary_bp
    from app.notifications import notifications_bp
    from app.requests import requests_bp
    from app.api.v1 import api_v1_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(students_bp, url_prefix='/students')
    app.register_blueprint(teachers_bp, url_prefix='/teachers')
    app.register_blueprint(parents_bp, url_prefix='/parents')
    app.register_blueprint(classes_bp, url_prefix='/classes')
    app.register_blueprint(batches_bp, url_prefix='/batches')
    app.register_blueprint(subjects_bp, url_prefix='/subjects')
    app.register_blueprint(fees_bp, url_prefix='/fees')
    app.register_blueprint(attendance_bp, url_prefix='/attendance')
    app.register_blueprint(timetable_bp, url_prefix='/timetable')
    app.register_blueprint(exams_bp, url_prefix='/exams')
    app.register_blueprint(assignments_bp, url_prefix='/assignments')
    app.register_blueprint(materials_bp, url_prefix='/materials')
    app.register_blueprint(announcements_bp, url_prefix='/announcements')
    app.register_blueprint(admissions_bp, url_prefix='/admissions')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    app.register_blueprint(audit_bp, url_prefix='/audit')
    app.register_blueprint(diary_bp, url_prefix='/diary')
    app.register_blueprint(notifications_bp, url_prefix='/notifications')
    app.register_blueprint(requests_bp, url_prefix='/requests')
    
    # Exclude CSRF for REST API blueprint
    csrf.exempt(api_v1_bp)
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')

    return app
