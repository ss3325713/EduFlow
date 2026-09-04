from flask import Blueprint

materials_bp = Blueprint('materials', __name__)

from app.materials import routes
