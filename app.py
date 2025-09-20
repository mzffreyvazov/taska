# app.py - Flask app using external HTML templates
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash, get_flashed_messages
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import json
from datetime import datetime
import uuid
import tempfile
from pathlib import Path

# Get the directory where this script is located
BASE_DIR = Path(__file__).parent.absolute()
UPLOAD_DIR = BASE_DIR / 'uploads'

# Create directories if they don't exist
try:
    UPLOAD_DIR.mkdir(exist_ok=True)
    print(f"✓ Upload folder: {UPLOAD_DIR}")
except Exception as e:
    # Fallback to temp directory for uploads
    UPLOAD_DIR = Path(tempfile.gettempdir()) / 'ai_system_uploads'
    UPLOAD_DIR.mkdir(exist_ok=True)
    print(f"⚠ Using temp upload folder: {UPLOAD_DIR}")

print(f"Working directory: {BASE_DIR}")
print(f"Upload folder: {UPLOAD_DIR}")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'azerbaijan-government-ai-system-2025'
app.config['UPLOAD_FOLDER'] = str(UPLOAD_DIR)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Try to import AI systems (optional)
try:
    from gemini_integration import EnhancedOpinionGenerator
    GEMINI_AVAILABLE = True
    print("✓ Gemini integration loaded")
except ImportError as e:
    print(f"✗ Gemini integration not available: {e}")
    GEMINI_AVAILABLE = False

try:
    from az_hierarchical_chunking import HybridSearchEngine, ChunkObject
    CHUNKING_AVAILABLE = True
    print("✓ Chunking system loaded")
except ImportError as e:
    print(f"✗ Chunking system not available: {e}")
    CHUNKING_AVAILABLE = False

# Database path resolution - try multiple locations
def get_database_path():
    """Find a writable location for the database"""
    possible_paths = [
        # Current directory
        Path.cwd() / 'government_ai_system.db',
        # User's home directory
        Path.home() / 'government_ai_system.db',
        # Temp directory
        Path(tempfile.gettempdir()) / 'government_ai_system.db',
        # Desktop (if accessible)
        Path.home() / 'Desktop' / 'government_ai_system.db'
    ]

    for db_path in possible_paths:
        try:
            # Test if we can create/write to this location
            test_conn = sqlite3.connect(str(db_path))
            test_conn.execute('CREATE TABLE IF NOT EXISTS test_table (id INTEGER)')
            test_conn.execute('DROP TABLE test_table')
            test_conn.close()
            print(f"✓ Database location: {db_path}")
            return db_path
        except Exception as e:
            print(f"✗ Cannot use {db_path}: {e}")
            continue

    # If all else fails, use in-memory database (will be lost on restart)
    print("⚠ Using in-memory database (data will be lost on restart)")
    return ':memory:'

DATABASE_PATH = get_database_path()
print(f"Database path: {DATABASE_PATH}")

def init_database():
    """Initialize the database"""
    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()

        # Users table
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS users
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           username TEXT UNIQUE NOT NULL,
                           password_hash TEXT NOT NULL,
                           role TEXT DEFAULT 'admin',
                           created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       )
                       ''')

        # Submitted documents table
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS submitted_documents
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           document_id TEXT UNIQUE NOT NULL,
                           title TEXT NOT NULL,
                           content TEXT NOT NULL,
                           comments TEXT,
                           submitter_name TEXT,
                           submitter_email TEXT,
                           submitter_organization TEXT,
                           file_path TEXT,
                           status TEXT DEFAULT 'pending',
                           submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       )
                       ''')

        # AI Analysis results table
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS ai_analysis
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           document_id TEXT NOT NULL,
                           decision TEXT NOT NULL,
                           analysis_data TEXT NOT NULL,
                           formatted_opinion TEXT NOT NULL,
                           chunks_referenced INTEGER DEFAULT 0,
                           analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                           FOREIGN KEY (document_id) REFERENCES submitted_documents (document_id)
                       )
                       ''')

        # Strategy documents table
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS strategy_documents
                       (
                           id INTEGER PRIMARY KEY AUTOINCREMENT,
                           document_name TEXT NOT NULL,
                           file_path TEXT NOT NULL,
                           chunks_count INTEGER DEFAULT 0,
                           uploaded_by TEXT NOT NULL,
                           uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                       )
                       ''')

        # Create default admin user
        cursor.execute("SELECT * FROM users WHERE username = 'admin'")
        if not cursor.fetchone():
            admin_password = generate_password_hash('admin123')
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                ('admin', admin_password, 'admin')
            )
            print("✓ Default admin user created (admin/admin123)")

        conn.commit()
        conn.close()
        print("✓ Database initialized successfully")
        return True
    except Exception as e:
        print(f"✗ Database initialization failed: {e}")
        return False

# Initialize AI systems
search_engine = None
ai_generator = None

def initialize_ai_systems():
    """Initialize AI systems"""
    global search_engine, ai_generator

    if CHUNKING_AVAILABLE:
        try:
            search_engine = HybridSearchEngine(
                db_path=str(BASE_DIR / "azerbaijani_chunks.db"),
                force_rebuild=False
            )
            stats = search_engine.get_database_stats()
            print(f"✓ Search engine initialized with {stats['total_chunks']} chunks")
        except Exception as e:
            print(f"✗ Search engine initialization failed: {e}")

    if GEMINI_AVAILABLE and search_engine:
        try:
            ai_generator = EnhancedOpinionGenerator(
                api_key=os.getenv("GEMINI_API_KEY", "AIzaSyAkGFBA12GztJUXSx9CA9kUwFG0pfJTOjw"),
                db_path=str(BASE_DIR / "azerbaijani_chunks.db")
            )
            print("✓ AI generator initialized")
        except Exception as e:
            print(f"✗ AI generator initialization failed: {e}")

def get_db_connection():
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'doc', 'docx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_file(file_path):
    """Extract text from uploaded file"""
    extension = file_path.split('.')[-1].lower()

    if extension == 'txt':
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()

    return f"File content ({extension} format)"

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/submit', methods=['POST'])
def submit_document():
    try:
        title = request.form.get('title', '').strip()
        if not title:
            return jsonify({'success': False, 'error': 'Sənəd başlığı tələb olunur'})

        file = request.files.get('document')
        document_text = request.form.get('document_text', '').strip()

        if not file and not document_text:
            return jsonify({'success': False, 'error': 'Sənəd faylı və ya mətn tələb olunur'})

        document_id = str(uuid.uuid4())
        file_path = None

        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = UPLOAD_DIR / f"{document_id}_{filename}"
            file.save(str(file_path))

            extracted_text = extract_text_from_file(str(file_path))
            if document_text:
                document_text = f"{document_text}\n\n--- Fayl məzmunu ---\n{extracted_text}"
            else:
                document_text = extracted_text

        if not document_text or len(document_text.strip()) < 20:
            return jsonify({'success': False, 'error': 'Sənəd məzmunu çox qısadır'})

        conn = get_db_connection()
        conn.execute('''
                     INSERT INTO submitted_documents
                     (document_id, title, content, comments, submitter_name, submitter_email,
                      submitter_organization, file_path, status)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                     ''', (document_id, title, document_text, request.form.get('comments', ''),
                           request.form.get('submitter_name', ''), request.form.get('submitter_email', ''),
                           request.form.get('submitter_organization', ''), str(file_path) if file_path else None,
                           'pending'))
        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Sənəd uğurla təqdim edildi', 'document_id': document_id})

    except Exception as e:
        return jsonify({'success': False, 'error': f'Xəta baş verdi: {str(e)}'})

@app.route('/admin')
def admin_login():
    if 'user_id' in session:
        return redirect(url_for('admin_dashboard'))
    return render_template('admin_login.html')

@app.route('/admin/login', methods=['POST'])
def admin_login_post():
    username = request.form.get('username')
    password = request.form.get('password')

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['username'] = user['username']
        return redirect(url_for('admin_dashboard'))
    else:
        flash('Yanlış istifadəçi adı və ya parol')
        return redirect(url_for('admin_login'))

@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()

    documents = conn.execute('''
                             SELECT sd.*, aa.decision, aa.analyzed_at
                             FROM submitted_documents sd
                                      LEFT JOIN ai_analysis aa ON sd.document_id = aa.document_id
                             ORDER BY sd.submitted_at DESC
                             ''').fetchall()

    strategy_docs = conn.execute('SELECT * FROM strategy_documents ORDER BY uploaded_at DESC').fetchall()

    conn.close()

    analyzed_count = sum(1 for doc in documents if doc['decision'])
    pending_count = sum(1 for doc in documents if not doc['decision'])

    return render_template('admin_dashboard.html',
                         documents=documents,
                         strategy_docs=strategy_docs,
                         analyzed_count=analyzed_count,
                         pending_count=pending_count)

@app.route('/admin/analyze/<document_id>')
def analyze_document(document_id):
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))

    if not ai_generator:
        flash('AI sistemi əlçatan deyil')
        return redirect(url_for('admin_dashboard'))

    try:
        conn = get_db_connection()
        document = conn.execute('SELECT * FROM submitted_documents WHERE document_id = ?', (document_id,)).fetchone()

        if not document:
            flash('Sənəd tapılmadı')
            return redirect(url_for('admin_dashboard'))

        existing_analysis = conn.execute('SELECT * FROM ai_analysis WHERE document_id = ?', (document_id,)).fetchone()

        if existing_analysis:
            flash('Bu sənəd artıq təhlil edilib')
            return redirect(url_for('admin_dashboard'))

        result = ai_generator.generate_comprehensive_opinion(
            document_text=document['content'],
            document_title=document['title'],
            ministry_name="İqtisadiyyat Nazirliyi"
        )

        if result['success']:
            conn.execute('''
                         INSERT INTO ai_analysis
                         (document_id, decision, analysis_data, formatted_opinion, chunks_referenced)
                         VALUES (?, ?, ?, ?, ?)
                         ''', (document_id, result['decision']['status'], json.dumps(result['opinion']),
                               result['formatted_opinion'], result['existing_chunks_referenced']))

            conn.execute('UPDATE submitted_documents SET status = ? WHERE document_id = ?', ('analyzed', document_id))
            conn.commit()
            flash('Sənəd uğurla təhlil edildi')
        else:
            flash(f'Təhlil xətası: {result["error"]}')

        conn.close()

    except Exception as e:
        flash(f'Xəta baş verdi: {str(e)}')

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/view_analysis/<document_id>')
def view_analysis(document_id):
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))

    conn = get_db_connection()
    document = conn.execute('SELECT * FROM submitted_documents WHERE document_id = ?', (document_id,)).fetchone()
    analysis = conn.execute('SELECT * FROM ai_analysis WHERE document_id = ?', (document_id,)).fetchone()
    conn.close()

    if not document:
        flash('Sənəd tapılmadı')
        return redirect(url_for('admin_dashboard'))

    return render_template('view_analysis.html', document=document, analysis=analysis)

@app.route('/admin/upload_strategy', methods=['POST'])
def upload_strategy_document():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))

    global search_engine

    try:
        file = request.files.get('strategy_file')
        document_name = request.form.get('document_name', '').strip()

        if not file or not file.filename:
            flash('Fayl seçilməlidir')
            return redirect(url_for('admin_dashboard'))

        if not document_name:
            document_name = file.filename

        if not allowed_file(file.filename):
            flash('Dəstəklənməyən fayl formatı')
            return redirect(url_for('admin_dashboard'))

        filename = secure_filename(file.filename)
        file_path = UPLOAD_DIR / f"strategy_{filename}"
        file.save(str(file_path))

        text_content = extract_text_from_file(str(file_path))

        if len(text_content.strip()) < 100:
            flash('Sənəd məzmunu çox qısadır')
            return redirect(url_for('admin_dashboard'))

        chunks_count = 0

        if CHUNKING_AVAILABLE:
            # Simple chunking - split by paragraphs
            sections = text_content.split('\n\n')
            chunks = []

            for i, section in enumerate(sections):
                if len(section.strip()) > 50:
                    chunk = ChunkObject(
                        title=f"{document_name} - Bölmə {i + 1}",
                        content=section.strip(),
                        level=0,
                        section_number=str(i + 1),
                        chunk_type="content"
                    )
                    chunks.append(chunk)

            if chunks:
                if search_engine:
                    search_engine.add_chunks(chunks)
                    chunks_count = len(chunks)
                    flash(f'Sənəd uğurla yükləndi və {chunks_count} chunk yaradıldı')
                else:
                    search_engine = HybridSearchEngine(
                        chunks=chunks,
                        db_path=str(BASE_DIR / "azerbaijani_chunks.db"),
                        force_rebuild=False
                    )
                    chunks_count = len(chunks)
                    flash(f'Axtarış sistemi {chunks_count} chunk ilə yaradıldı')

                # Reinitialize AI generator
                global ai_generator
                if GEMINI_AVAILABLE:
                    try:
                        ai_generator = EnhancedOpinionGenerator(
                            api_key=os.getenv("GEMINI_API_KEY", "AIzaSyAkGFBA12GztJUXSx9CA9kUwFG0pfJTOjw"),
                            db_path=str(BASE_DIR / "azerbaijani_chunks.db")
                        )
                        print("AI generator reinitialized")
                    except Exception as e:
                        print(f"AI generator reinitialization failed: {e}")
            else:
                flash('Chunk yaradıla bilmədi')
        else:
            flash('Chunk sistemi əlçatan deyil')

        conn = get_db_connection()
        conn.execute('''
                     INSERT INTO strategy_documents
                         (document_name, file_path, chunks_count, uploaded_by)
                     VALUES (?, ?, ?, ?)
                     ''', (document_name, str(file_path), chunks_count, session['username']))
        conn.commit()
        conn.close()

    except Exception as e:
        flash(f'Xəta baş verdi: {str(e)}')

    return redirect(url_for('admin_dashboard'))

# Template context processor to make session available in templates
@app.context_processor
def inject_session():
    return dict(session=session, get_flashed_messages=get_flashed_messages)

if __name__ == '__main__':
    print("🚀 Starting Government AI Analysis System...")
    print("=" * 60)

    # Initialize database
    if not init_database():
        print("❌ Database initialization failed!")
        exit(1)

    # Initialize AI systems
    initialize_ai_systems()

    print("\n" + "=" * 60)
    print("✅ System Ready!")
    print(f"📁 Working Directory: {BASE_DIR}")
    print(f"📂 Upload Folder: {UPLOAD_DIR}")
    print(f"🗄️ Database: {DATABASE_PATH}")
    print(f"🤖 AI System: {'✅ Available' if ai_generator else '❌ Not Available'}")
    print(f"🔍 Search Engine: {'✅ Available' if search_engine else '❌ Not Available'}")
    print("\n👤 Admin Login:")
    print("   Username: admin")
    print("   Password: admin123")
    print("\n🌐 Server: http://localhost:5000")
    print("=" * 60)

    app.run(debug=True, host='127.0.0.1', port=5000)