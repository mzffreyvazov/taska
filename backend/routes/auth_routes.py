# routes/auth_routes.py
"""Authentication routes with cookie-based sessions"""
from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt,
    set_access_cookies, set_refresh_cookies, 
    unset_jwt_cookies, get_csrf_token
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import re

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

def init_auth_routes(db_manager):
    """Initialize auth routes with database manager"""
    
    @auth_bp.route('/register', methods=['POST'])
    def register():
        """Register new user"""
        try:
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            email = data.get('email', '').strip()
            
            # Validation
            if not username or not password:
                return jsonify({'error': 'Username və password tələb olunur'}), 400
            
            if len(username) < 3:
                return jsonify({'error': 'Username ən azı 3 simvol olmalıdır'}), 400
            
            if len(password) < 6:
                return jsonify({'error': 'Password ən azı 6 simvol olmalıdır'}), 400
            
            if email and not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
                return jsonify({'error': 'Email formatı yanlışdır'}), 400
            
            # Check if user exists
            existing_user = db_manager.get_user_by_username(username)
            if existing_user:
                return jsonify({'error': 'Bu username artıq mövcuddur'}), 400
            
            # Create user
            password_hash = generate_password_hash(password)
            user_id = db_manager.create_user(username, password_hash, email)
            
            # Create tokens
            access_token = create_access_token(
                identity=user_id,
                additional_claims={'role': 'user', 'username': username}
            )
            refresh_token = create_refresh_token(
                identity=user_id,
                additional_claims={'role': 'user', 'username': username}
            )
            
            # Create response and set cookies
            response = make_response(jsonify({
                'message': 'Qeydiyyat uğurlu',
                'user': {
                    'id': user_id,
                    'username': username,
                    'role': 'user',
                    'email': email
                }
            }), 201)
            
            # Set JWT cookies
            set_access_cookies(response, access_token)
            set_refresh_cookies(response, refresh_token)
            
            # Save session in database
            expires_at = datetime.utcnow() + timedelta(days=30)
            db_manager.save_refresh_token(user_id, refresh_token, expires_at.isoformat())
            
            return response
            
        except Exception as e:
            return jsonify({'error': f'Qeydiyyat xətası: {str(e)}'}), 500
    
    @auth_bp.route('/login', methods=['POST'])
    def login():
        """Login user"""
        try:
            data = request.get_json()
            username = data.get('username', '').strip()
            password = data.get('password', '').strip()
            
            if not username or not password:
                return jsonify({'error': 'Username və password tələb olunur'}), 400
            
            # Get user
            user = db_manager.get_user_by_username(username)
            if not user or not check_password_hash(user['password_hash'], password):
                return jsonify({'error': 'Yanlış username və ya password'}), 401
            
            # Create tokens
            access_token = create_access_token(
                identity=user['id'],
                additional_claims={
                    'role': user['role'],
                    'username': user['username']
                }
            )
            refresh_token = create_refresh_token(
                identity=user['id'],
                additional_claims={
                    'role': user['role'],
                    'username': user['username']
                }
            )
            
            # Create response
            response = make_response(jsonify({
                'message': 'Giriş uğurlu',
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role'],
                    'email': user.get('email')
                }
            }))
            
            # Set JWT cookies
            set_access_cookies(response, access_token)
            set_refresh_cookies(response, refresh_token)
            
            # Save session in database
            expires_at = datetime.utcnow() + timedelta(days=30)
            db_manager.save_refresh_token(user['id'], refresh_token, expires_at.isoformat())
            
            return response
            
        except Exception as e:
            return jsonify({'error': f'Login xətası: {str(e)}'}), 500
    
    @auth_bp.route('/refresh', methods=['POST'])
    @jwt_required(refresh=True, locations=['cookies', 'headers'])
    def refresh():
        """Refresh access token"""
        try:
            user_id = get_jwt_identity()
            claims = get_jwt()
            
            # Get user
            user = db_manager.get_user_by_id(user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            # Create new access token
            access_token = create_access_token(
                identity=user['id'],
                additional_claims={
                    'role': user['role'],
                    'username': user['username']
                }
            )
            
            # Create response and set cookie
            response = make_response(jsonify({
                'message': 'Token refreshed',
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role'],
                    'email': user.get('email')
                }
            }))
            
            set_access_cookies(response, access_token)
            
            return response
            
        except Exception as e:
            return jsonify({'error': f'Refresh xətası: {str(e)}'}), 500
    
    @auth_bp.route('/logout', methods=['POST'])
    @jwt_required(optional=True, locations=['cookies', 'headers'])
    def logout():
        """Logout user"""
        try:
            # Clear cookies
            response = make_response(jsonify({'message': 'Çıxış edildi'}))
            unset_jwt_cookies(response)
            
            # Try to clean up database token
            try:
                user_id = get_jwt_identity()
                if user_id:
                    # Clean up any stored tokens
                    db_manager.execute_query(
                        "DELETE FROM refresh_tokens WHERE user_id = ?",
                        (user_id,)
                    )
            except:
                pass
            
            return response
            
        except Exception as e:
            return jsonify({'error': f'Logout xətası: {str(e)}'}), 500
    
    @auth_bp.route('/me', methods=['GET'])
    @jwt_required(locations=['cookies', 'headers'])
    def get_current_user():
        """Get current user info"""
        try:
            user_id = get_jwt_identity()
            claims = get_jwt()
            
            user = db_manager.get_user_by_id(user_id)
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            return jsonify({
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role'],
                    'email': user.get('email'),
                    'created_at': user.get('created_at')
                }
            })
            
        except Exception as e:
            return jsonify({'error': f'User info xətası: {str(e)}'}), 500
    
    @auth_bp.route('/check', methods=['GET'])
    @jwt_required(optional=True, locations=['cookies', 'headers'])
    def check_auth():
        """Check authentication status"""
        try:
            user_id = get_jwt_identity()
            
            if not user_id:
                return jsonify({'authenticated': False}), 200
            
            user = db_manager.get_user_by_id(user_id)
            if not user:
                return jsonify({'authenticated': False}), 200
            
            return jsonify({
                'authenticated': True,
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role'],
                    'email': user.get('email')
                }
            })
            
        except Exception as e:
            return jsonify({'authenticated': False, 'error': str(e)}), 200
    
    return auth_bp