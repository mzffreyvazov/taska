# routes/contact_routes.py
"""Routes for contact search, spell check, and confidence scoring endpoints"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required

contact_bp = Blueprint('contact', __name__, url_prefix='/api')

def init_contact_routes(hybrid_service):
    """Initialize contact search routes"""
    @contact_bp.route('/search-contact', methods=['POST'])
    @jwt_required(locations=['cookies', 'headers'])
    def search_contact():
        data = request.get_json() or {}
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'Sorğu tələb olunur'}), 400
        results = hybrid_service.search(query)
        return jsonify({'results': results}), 200

    @contact_bp.route('/spell-check', methods=['POST'])
    @jwt_required(locations=['cookies', 'headers'])
    def spell_check():
        data = request.get_json() or {}
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'Sorğu tələb olunur'}), 400
        corrections = hybrid_service.spell_check(query)
        return jsonify({'corrections': corrections}), 200

    @contact_bp.route('/confidence', methods=['POST'])
    @jwt_required(locations=['cookies', 'headers'])
    def confidence():
        data = request.get_json() or {}
        query = data.get('query', '').strip()
        if not query:
            return jsonify({'error': 'Sorğu tələb olunur'}), 400
        score = hybrid_service.confidence_score(query)
        return jsonify({'confidence': score}), 200

    return contact_bp
