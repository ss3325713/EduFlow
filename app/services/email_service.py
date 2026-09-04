import smtplib
import threading
import re
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, render_template
from app.extensions import db
from app.models.email_log import EmailLog
from app.models.email_preference import EmailPreference, EmailCategory
from app.services.audit_service import log_action

logger = logging.getLogger('eduflow.email')

class EmailService:
    @staticmethod
    def is_valid_email(email):
        if not email:
            return False
        pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
        return bool(re.match(pattern, email.strip()))

    @staticmethod
    def _send_smtp_message(app_config, msg, recipient, category, subject, template_name, user_id):
        smtp_server = app_config.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = app_config.get('SMTP_PORT', 587)
        smtp_username = app_config.get('SMTP_USERNAME', 'noreply.vista@gmail.com')
        smtp_password = app_config.get('SMTP_PASSWORD', '')
        smtp_use_tls = app_config.get('SMTP_USE_TLS', True)
        sender = app_config.get('MAIL_FROM_ADDRESS', 'noreply.vista@gmail.com')

        status = 'sent'
        failure_reason = None

        try:
            # Check if test mode or dummy credentials
            if app_config.get('TESTING') or not smtp_password:
                logger.info(f"[EmailService TEST/MOCK] Simulating email to {recipient} | Subject: {subject}")
                status = 'sent'
            else:
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
                if smtp_use_tls:
                    server.starttls()
                if smtp_username and smtp_password:
                    server.login(smtp_username, smtp_password)
                server.sendmail(sender, [recipient], msg.as_string())
                server.quit()
                logger.info(f"[EmailService SENT] Successfully sent email to {recipient} | Subject: {subject}")
        except Exception as e:
            status = 'failed'
            failure_reason = str(e)
            logger.error(f"[EmailService ERROR] Failed to send email to {recipient}: {e}")

        return status, failure_reason

    @classmethod
    def send_email(cls, to_email, subject, template_name, context=None, reply_to=None, category=EmailCategory.AUTHENTICATION, user_id=None, async_send=True):
        if not to_email or not cls.is_valid_email(to_email):
            logger.warning(f"[EmailService] Invalid recipient email address: {to_email}")
            return False, "Invalid email address"

        to_email = to_email.strip().lower()

        # Check user notification preference if user_id is provided
        if user_id and not EmailPreference.is_category_enabled(user_id, category):
            logger.info(f"[EmailService PREFERENCE] Email skipped for user {user_id} (Category {category} disabled)")
            return True, "Skipped due to user email preference"

        context = context or {}
        context.setdefault('app_name', 'EduFlow Academy')

        app = current_app._get_current_object()
        app_config = app.config

        mail_from_address = app_config.get('MAIL_FROM_ADDRESS', 'noreply.vista@gmail.com')
        mail_from_name = app_config.get('MAIL_FROM_NAME', 'EduFlow Notifications')

        # Build MIME Message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{mail_from_name} <{mail_from_address}>"
        msg['To'] = to_email

        if reply_to and cls.is_valid_email(reply_to):
            msg['Reply-To'] = reply_to.strip()

        # Render HTML & Plain text template content
        html_content = ""
        text_content = ""

        try:
            html_content = render_template(f"emails/{template_name}.html", **context)
        except Exception:
            # Fallback inline layout if template missing
            html_content = f"<h3>{subject}</h3><p>{context.get('message', '')}</p><br><p>Sent via EduFlow Academy</p>"

        try:
            text_content = render_template(f"emails/{template_name}.txt", **context)
        except Exception:
            # Strip tags for plain text fallback
            text_content = re.sub('<[^<]+?>', '', html_content)

        msg.attach(MIMEText(text_content, 'plain'))
        msg.attach(MIMEText(html_content, 'html'))

        def _worker(app_obj):
            with app_obj.app_context():
                status, failure_reason = cls._send_smtp_message(
                    app_config, msg, to_email, category, subject, template_name, user_id
                )
                try:
                    log_entry = EmailLog(
                        recipient_email=to_email,
                        sender_email=mail_from_address,
                        category=category,
                        subject=subject,
                        template_name=template_name,
                        status=status,
                        failure_reason=failure_reason,
                        user_id=user_id
                    )
                    db.session.add(log_entry)
                    db.session.commit()

                    log_action(
                        action='EMAIL_SENT' if status == 'sent' else 'EMAIL_FAILED',
                        target_type='EmailLog',
                        target_id=log_entry.id,
                        details=f"Email to {to_email} ({category}): {subject} [{status}]",
                        user_id=user_id
                    )
                except Exception as log_err:
                    db.session.rollback()
                    logger.error(f"[EmailService LOG ERROR] Could not log email sending result: {log_err}")

        if async_send:
            thread = threading.Thread(target=_worker, args=(app,))
            thread.daemon = True
            thread.start()
            return True, "Email queued for delivery"
        else:
            _worker(app)
            return True, "Email process completed"
