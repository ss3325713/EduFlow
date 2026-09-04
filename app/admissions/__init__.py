from flask import Blueprint

admissions_bp = Blueprint('admissions', __name__)

from app.admissions import routes
