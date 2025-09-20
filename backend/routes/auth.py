from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from services.user_service import register, authenticate

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register_user():
    data = request.json
    if register(data['email'], data['password'], data.get('role', 'işçi')):
        return jsonify({"message": "Qeydiyyatdan keçildi."}), 201
    return jsonify({"error": "Bu email artıq mövcuddur."}), 400

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json
    user = authenticate(data['email'], data['password'])
    if user:
        token = create_access_token(identity=data['email'])
        return jsonify({"access_token": token, "role": user["role"]})
    return jsonify({"error": "Yanlış email və ya şifrə."}), 401