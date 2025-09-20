# routes/simple_auth_routes.py
"""Simple session-based authentication"""
from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import re

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

def init_simple_auth_routes(db_manager):
    """Initialize simple session-based auth routes"""
    
    def login_required(f):
        """Decorator to require login"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            return f(*args, **kwargs)
        return decorated_function
    
    def admin_required(f):
        """Decorator to require admin role"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return jsonify({'error': 'Authentication required'}), 401
            if session.get('role') != 'admin':
                return jsonify({'error': 'Admin access required'}), 403
            return f(*args, **kwargs)
        return decorated_function
    
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
            
            # Check if user exists
            existing_user = db_manager.get_user_by_username(username)
            if existing_user:
                return jsonify({'error': 'Bu username artıq mövcuddur'}), 400
            
            # Create user
            password_hash = generate_password_hash(password)
            user_id = db_manager.create_user(username, password_hash, email)
            
            # Set session
            session['user_id'] = user_id
            session['username'] = username
            session['role'] = 'user'
            session.permanent = True
            
            return jsonify({
                'message': 'Qeydiyyat uğurlu',
                'user': {
                    'id': user_id,
                    'username': username,
                    'role': 'user',
                    'email': email
                }
            }), 201
            
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
            
            # Set session
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session.permanent = True
            
            return jsonify({
                'message': 'Giriş uğurlu',
                'user': {
                    'id': user['id'],
                    'username': user['username'],
                    'role': user['role'],
                    'email': user.get('email')
                }
            })
            
        except Exception as e:
            return jsonify({'error': f'Login xətası: {str(e)}'}), 500
    
    @auth_bp.route('/logout', methods=['POST'])
    def logout():
        """Logout user"""
        session.clear()
        return jsonify({'message': 'Çıxış edildi'})
    
    @auth_bp.route('/check', methods=['GET'])
    def check_auth():
        """Check authentication status"""
        if 'user_id' in session:
            return jsonify({
                'authenticated': True,
                'user': {
                    'id': session['user_id'],
                    'username': session['username'],
                    'role': session.get('role', 'user')
                }
            })
        
        return jsonify({'authenticated': False})
    
    @auth_bp.route('/me', methods=['GET'])
    @login_required
    def get_current_user():
        """Get current user info"""
        user_id = session['user_id']
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
    
    # Export decorators for use in other routes
    auth_bp.login_required = login_required
    auth_bp.admin_required = admin_required
    
    return auth_bp