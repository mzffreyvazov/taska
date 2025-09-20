# backend/routes/files.py

from flask import Blueprint, request, send_from_directory, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
import os
import logging

from services.file_service import save_file_metadata, get_file_metadata, file_exists_in_db
from services.user_service import get_user_by_email
from utils.pdf_reader import extract_text_from_pdf
from utils.docx_reader import extract_text_from_docx
from utils.json_reader import extract_text_from_json
from utils.chunker import VectorDB

# Blueprint yaradılır
files_bp = Blueprint('files', __name__)

# Fayl ekstraktorları
EXTRACTORS = {
    'pdf': extract_text_from_pdf,
    'docx': extract_text_from_docx,
    'json': extract_text_from_json
}

# Vektor DB
vector_db = VectorDB()

# Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@files_bp.route('/upload', methods=['POST'])
@jwt_required()
def upload_file():
    """
    Yalnız admin fayl yükləyə bilər.
    Fayl `documents/` qovluğuna yazılır, meta məlumat DB-yə, mətn vektor bazasına daxil edilir.
    """
    current_user_email = get_jwt_identity()

    # Admin yoxlaması
    user = get_user_by_email(current_user_email)
    if not user or user[2] != 'admin':  # user[2] = role
        return jsonify({"error": "Bu əməliyyat üçün icazəniz yoxdur."}), 403

    if 'file' not in request.files:
        return jsonify({"error": "Fayl seçilməyib."}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Fayl adı boşdur."}), 400

    # Fayl adı təmizlənir
    filename = file.filename.strip().replace(" ", "_")
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

    # Uzantı yoxlanılır
    if '.' not in filename:
        return jsonify({"error": "Fayl uzantısı yoxdur."}), 400

    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in EXTRACTORS:
        return jsonify({"error": f"Yalnız PDF, DOCX və JSON faylları dəstəklənir. Siz {ext.upper()} faylı yükləmisiniz."}), 400

    # Eyni adda faylın olub-olmaması yoxlanılır
    if file_exists_in_db(filename):
        return jsonify({"error": "Bu adda fayl artıq mövcuddur. Zəhmət olmasa fayl adını dəyişin."}), 400

    try:
        # Faylın mətni çıxarılır
        file.save(filepath)
        text = EXTRACTORS[ext](filepath)

        if not text.strip():
            os.remove(filepath)  # Səhv fayl silinir
            return jsonify({"error": "Fayldan mətn çıxarıla bilmədi. Fayl korrode ola bilər."}), 400

        # Vektor bazasına əlavə edilir
        try:
            vector_db.add_document(text, doc_id=filename)
            logger.info(f"Vektor bazasına əlavə edildi: {filename}")
        except Exception as ve:
            os.remove(filepath)
            logger.error(f"Vektor bazasına əlavə edilərkən xəta: {ve}")
            return jsonify({"error": "Vektor bazasına əlavə edilərkən xəta."}), 500

        # Meta məlumat DB-yə yazılır
        original_name = file.filename
        description = request.form.get("description", f"{ext.upper()} faylı")  # Təsvir formdan gəlir
        save_file_metadata(
            filename=filename,
            original_name=original_name,
            file_type=ext,
            uploaded_by=current_user_email,
            description=description  # Burada təsvir əlavə olunur
        )

        logger.info(f"Fayl yükləndi: {filename} (tərəfindən: {current_user_email})")
        return jsonify({
            "message": f"Fayl uğurla yükləndi və indeksləndi: {filename}",
            "filename": filename,
            "original_name": original_name,
            "file_type": ext,
            "description": description
        }), 200

    except Exception as e:
        logger.error(f"Fayl yüklənərkən xəta: {e}")
        return jsonify({"error": "Fayl yüklənərkən xəta baş verdi."}), 500


@files_bp.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """
    İstifadəçi faylı endirə bilər.
    Yalnız mövcud fayllar endirilir.
    """
    try:
        # Meta məlumat bazasında var?
        if not file_exists_in_db(filename):
            return jsonify({"error": "Bu fayl mövcud deyil."}), 404

        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
    except Exception as e:
        logger.error(f"Fayl endirilərkən xəta: {e}")
        return jsonify({"error": "Fayl tapılmadı və ya endirilə bilmir."}), 404


@files_bp.route('/files', methods=['GET'])
@jwt_required()
def list_files():
    """
    Bütün faylların siyahısı.
    İstifadəçi üçün ictimai siyahı.
    """
    try:
        files = get_file_metadata()  # [(filename, original_name, file_type, category, description), ...]
        result = [
            {
                "filename": f[0],
                "original_name": f[1],
                "file_type": f[2],
                "category": f[3],
                "description": f[4]  # Təsvir də qayıdır
            }
            for f in files
        ]
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Fayl siyahısı alınarkən xəta: {e}")
        return jsonify({"error": "Fayl siyahısı alınarkən xəta."}), 500


@files_bp.route('/files/<category>', methods=['GET'])
@jwt_required()
def list_files_by_category(category):
    """
    Kategoriya üzrə fayllar (məs: /files/nda)
    """
    try:
        files = get_file_metadata(category=category)
        result = [
            {
                "filename": f[0],
                "original_name": f[1],
                "file_type": f[2],
                "category": f[3],
                "description": f[4]
            }
            for f in files
        ]
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Kategoriya üzrə fayllar alınarkən xəta: {e}")
        return jsonify({"error": "Fayllar alınarkən xəta."}), 500


@files_bp.route('/files/delete/<filename>', methods=['DELETE'])
@jwt_required()
def delete_file(filename):
    """
    Yalnız admin faylı silə bilər.
    1. Vektor bazasından silinir
    2. Fayl sisteminən silinir
    3. Meta məlumat DB-dən silinir
    """
    current_user_email = get_jwt_identity()
    user = get_user_by_email(current_user_email)
    if not user or user[2] != 'admin':
        return jsonify({"error": "Silmək üçün icazəniz yoxdur."}), 403

    try:
        # 1. Meta məlumat bazasında var?
        if not file_exists_in_db(filename):
            return jsonify({"error": "Bu fayl mövcud deyil."}), 404

        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)

        # 2. Fayl sisteminən silinir
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Fayl silindi: {filename}")
        else:
            return jsonify({"error": "Fayl sisteminən tapılmadı."}), 404

        # 3. Meta məlumat DB-dən silinir
        from services.file_service import delete_file_metadata
        if delete_file_metadata(filename):
            logger.info(f"Meta məlumat silindi: {filename}")
            return jsonify({"message": f"Fayl uğurla silindi: {filename}"}), 200
        else:
            return jsonify({"error": "Meta məlumat silinərkən xəta."}), 500

    except Exception as e:
        logger.error(f"Fayl silinərkən xəta: {e}")
        return jsonify({"error": "Fayl silinərkən xəta."}), 500