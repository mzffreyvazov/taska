from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.chat_service import get_chat_history, delete_chat
from services.chatbot_service import handle_query
import sqlite3

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat', methods=['POST'])
@jwt_required()
def chat():
    data = request.json
    query = data.get('query')
    session_id = data.get('session_id', 'default')
    email = get_jwt_identity()

    if not query:
        return jsonify({"response": "Sual boş ola bilməz.", "type": "text"}), 400

    try:
        response = handle_query(query, session_id, email)
        return jsonify(response), 200
    except Exception as e:
        print(f"Chat xətası: {e}")
        return jsonify({"response": "Cavab alınmadı.", "type": "text"}), 500

@chat_bp.route('/chats', methods=['GET'])
@jwt_required()
def list_chats():
    from services.user_service import authenticate
    user = authenticate(get_jwt_identity(), "dummy")
    with sqlite3.connect("data/chats.db") as conn:
        rows = conn.execute("SELECT DISTINCT session_id FROM chats WHERE user_id=?", (user["id"],)).fetchall()
        return jsonify([r[0] for r in rows])

@chat_bp.route('/chats', methods=['DELETE'])
@jwt_required()
def delete_user_chat():
    user_email = get_jwt_identity()
    from services.user_service import authenticate
    user = authenticate(user_email, "dummy")
    session_id = request.json.get("session_id")
    delete_chat(user["id"], session_id)
    return jsonify({"message": "Chat silindi."})