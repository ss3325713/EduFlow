from flask import Blueprint

diary_bp = Blueprint('diary', __name__)

from app.diary import routes
