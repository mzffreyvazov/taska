from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.user_service import get_all_users, update_user_role, delete_user

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
def list_users():
    user = get_jwt_identity()
    # Burada admin yoxlaması olmalıdır
    return jsonify(get_all_users())

@admin_bp.route('/users/role', methods=['POST'])
@jwt_required()
def change_role():
    data = request.json
    update_user_role(data['user_id'], data['role'])
    return jsonify({"message": "Rol dəyişdirildi."})

@admin_bp.route('/users', methods=['DELETE'])
@jwt_required()
def remove_user():
    user_id = request.json.get('user_id')
    delete_user(user_id)
    return jsonify({"message": "İstifadəçi silindi."})