from flask import Blueprint

assignments_bp = Blueprint('assignments', __name__)

from app.assignments import routes
