from flask import Blueprint

announcements_bp = Blueprint('announcements', __name__)

from app.announcements import routes
