from flask import Blueprint, request, jsonify

bp = Blueprint('routes', __name__)

@bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'msg': 'The api is healthy'}), 200
