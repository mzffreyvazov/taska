# app.py
"""Main Flask application"""
import os
from datetime import datetime
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_jwt_extended import JWTManager

# Import configuration
from config import get_config

# Import utilities
from utils.database import DatabaseManager

# Import services
from services.enhanced_rag_service import EnhancedRAGServiceV2
from services.file_processor import FileProcessor

# Import routes
from routes.auth_routes import init_auth_routes
from routes.document_routes import init_document_routes
from routes.chat_routes import init_chat_routes

def create_app(config_name=None):
    """Create and configure Flask application"""
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load configuration
    config = get_config()
    app.config.from_object(config)
    
    # Ensure JWT configuration is set properly
    app.config['JWT_TOKEN_LOCATION'] = ['cookies', 'headers']
    app.config['JWT_COOKIE_SECURE'] = False  # Set True in production
    app.config['JWT_COOKIE_CSRF_PROTECT'] = False
    app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
    app.config['JWT_REFRESH_COOKIE_NAME'] = 'refresh_token_cookie'
    app.config['JWT_COOKIE_SAMESITE'] = 'Lax'
    
    # Initialize JWT after config
    jwt = JWTManager(app)
    
    # Configure CORS with credentials support
    CORS(app, 
         origins=config.CORS_ORIGINS,
         supports_credentials=True,
         allow_headers=['Content-Type', 'Authorization', 'Accept'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
         expose_headers=['Content-Type', 'Authorization']
    )
    
    # Create necessary directories
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(config.VECTOR_DB_PATH, exist_ok=True)
    
    # Initialize services
    db_manager = DatabaseManager(config.DATABASE_FILE)
    rag_service = EnhancedRAGServiceV2(config)
    
    # Register blueprints
    auth_bp = init_auth_routes(db_manager)
    docs_bp = init_document_routes(db_manager, rag_service, config)
    chat_bp = init_chat_routes(db_manager, rag_service, config)  # Pass config
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(chat_bp)
    
    # JWT error handlers
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({'error': 'Token müddəti bitib', 'code': 'token_expired'}), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({'error': 'Token yanlışdır', 'code': 'invalid_token'}), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({'error': 'Token tələb olunur', 'code': 'missing_token'}), 401
    
    # Debug endpoint - REMOVE IN PRODUCTION
    @app.route('/api/debug/headers', methods=['GET', 'POST'])
    def debug_headers():
        """Debug endpoint to check headers"""
        return jsonify({
            'headers': dict(request.headers),
            'authorization': request.headers.get('Authorization'),
            'method': request.method,
            'cookies': dict(request.cookies)
        })
    
    # Health check endpoint
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """System health check"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'services': {
                'database': 'active',
                'rag': 'active',
                'file_processor': FileProcessor().pdf_library or 'none'
            }
        })
    
    # System info endpoint
    @app.route('/api/system-info', methods=['GET'])
    def system_info():
        """System information"""
        # Get statistics
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) as count FROM users")
            user_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM documents")
            doc_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM conversations")
            conv_count = cursor.fetchone()['count']
            
            cursor.execute("SELECT COALESCE(SUM(file_size), 0) as total FROM documents")
            total_size = cursor.fetchone()['total']
        
        return jsonify({
            'status': 'running',
            'version': '2.0.0',
            'pdf_library': FileProcessor().pdf_library,
            'supported_formats': config.SUPPORTED_EXTENSIONS,
            'max_file_size_mb': config.MAX_FILE_SIZE // (1024 * 1024),
            'statistics': {
                'users': user_count,
                'documents': doc_count,
                'conversations': conv_count,
                'storage_bytes': total_size,
                'storage_mb': round(total_size / (1024 * 1024), 2) if total_size else 0
            },
            'ai_config': {
                'llm_model': config.LLM_MODEL,
                'embedding_model': config.EMBEDDING_MODEL,
                'chunk_size': config.CHUNK_SIZE,
                'search_results': config.SEARCH_RESULTS_COUNT
            }
        })
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint tapılmadı'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Server xətası'}), 500
    
    return app

# Create application
app = create_app()

if __name__ == '__main__':
    print("🚀 RAG Chatbot Backend Starting...")
    print("=" * 50)
    
    # Check configuration
    config = get_config()
    
    # Check PDF library
    from services.file_processor import FileProcessor
    processor = FileProcessor()
    if processor.pdf_library:
        print(f"✅ PDF Library: {processor.pdf_library}")
    else:
        print("⚠️  PDF Library: Not installed")
    
    # Check API key
    if config.GEMINI_API_KEY == "your-gemini-api-key":
        print("⚠️  IMPORTANT: Set GEMINI_API_KEY in .env file!")
    else:
        print("✅ Gemini API: Configured")
    
    print("=" * 50)
    print(f"📡 Server: http://localhost:5000")
    print(f"📚 API Docs: http://localhost:5000/api")
    print(f"🔐 Default admin: admin / admin123")
    print(f"📁 Supported formats: {', '.join(config.SUPPORTED_EXTENSIONS)}")
    print("=" * 50)
    
    # Run app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=config.DEBUG
    )