# utils/auth.py
"""Authentication and authorization utilities"""
from functools import wraps
from flask_jwt_extended import verify_jwt_in_request, get_jwt, get_jwt_identity
from flask import jsonify

def admin_required():
    """Decorator that requires admin role"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request(locations=['cookies', 'headers'])
            claims = get_jwt()
            if claims.get('role') != 'admin':
                return jsonify({'error': 'Admin access required'}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def optional_auth():
    """Decorator for optional authentication"""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                verify_jwt_in_request(optional=True)
            except:
                pass
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def get_current_user_id():
    """Get current user ID from JWT"""
    try:
        return get_jwt_identity()
    except:
        return None

def get_current_user_role():
    """Get current user role from JWT"""
    try:
        claims = get_jwt()
        return claims.get('role', 'user')
    except:
        return None