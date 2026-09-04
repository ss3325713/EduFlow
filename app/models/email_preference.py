from app.extensions import db

class EmailCategory:
    AUTHENTICATION = 'AUTHENTICATION'  # Mandatory
    SECURITY = 'SECURITY'              # Mandatory
    ACADEMIC = 'ACADEMIC'              # Optional
    INSTITUTIONAL = 'INSTITUTIONAL'    # Optional
    CLASS = 'CLASS'                    # Optional
    FINANCIAL = 'FINANCIAL'            # Optional
    ATTENDANCE = 'ATTENDANCE'          # Optional
    COMMUNICATION = 'COMMUNICATION'    # Optional

    OPTIONAL_CATEGORIES = [
        (ACADEMIC, 'Academic Updates & Resources'),
        (INSTITUTIONAL, 'General Announcements & News'),
        (CLASS, 'Class Schedule & Cancellation Alerts'),
        (FINANCIAL, 'Fee Payment Confirmations & Statements'),
        (ATTENDANCE, 'Absence & Attendance Alerts'),
        (COMMUNICATION, 'Teacher-to-Parent Messages')
    ]

    MANDATORY_CATEGORIES = {AUTHENTICATION, SECURITY}

class EmailPreference(db.Model):
    __tablename__ = 'email_preferences'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    category = db.Column(db.String(50), nullable=False)
    enabled = db.Column(db.Boolean, default=True, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'category', name='uix_user_email_category'),
    )

    user = db.relationship('User', backref=db.backref('email_preferences', lazy='dynamic', cascade='all, delete-orphan'))

    @staticmethod
    def is_category_enabled(user_id, category):
        if not user_id:
            return True
        if category in EmailCategory.MANDATORY_CATEGORIES:
            return True
        pref = EmailPreference.query.filter_by(user_id=user_id, category=category).first()
        return pref.enabled if pref else True

    @staticmethod
    def set_category_preference(user_id, category, enabled):
        if category in EmailCategory.MANDATORY_CATEGORIES:
            return  # Cannot disable mandatory categories
        pref = EmailPreference.query.filter_by(user_id=user_id, category=category).first()
        if not pref:
            pref = EmailPreference(user_id=user_id, category=category, enabled=enabled)
            db.session.add(pref)
        else:
            pref.enabled = enabled
        db.session.commit()

    def __repr__(self):
        return f'<EmailPreference user_id={self.user_id} category={self.category} enabled={self.enabled}>'
