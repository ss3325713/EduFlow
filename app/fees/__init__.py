from flask import Blueprint

fees_bp = Blueprint('fees', __name__)

from app.fees import routes
