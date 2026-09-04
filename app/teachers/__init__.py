from flask import Blueprint

teachers_bp = Blueprint('teachers', __name__)

from app.teachers import routes
