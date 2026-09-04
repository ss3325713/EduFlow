from flask import Blueprint

batches_bp = Blueprint('batches', __name__)

from app.batches import routes
