from flask import Blueprint

classes_bp = Blueprint('classes', __name__)

from app.classes import routes
