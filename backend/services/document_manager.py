# services/document_manager.py
"""Enhanced document management with types and templates"""
import os
import json
import shutil
from typing import List, Dict, Optional
from datetime import datetime, timezone

class DocumentManager:
    """Manage documents with types and templates"""
    
    # Document types
    DOCUMENT_TYPES = {
        'contact': 'Əlaqə məlumatları',
        'contract': 'Müqavilə',
        'vacation': 'Məzuniyyət',
        'business_trip': 'Ezamiyyət',
        'memorandum': 'Anlaşma memorandumu',
        'report': 'Hesabat',
        'letter': 'Məktub',
        'invoice': 'Qaimə',
        'other': 'Digər'
    }
    
    def __init__(self, db_manager, config):
        self.db_manager = db_manager
        self.config = config
        self.example_docs_path = 'example_docs'
        self.ensure_example_docs()
    
    def ensure_example_docs(self):
        """Ensure example documents directory exists with templates"""
        os.makedirs(self.example_docs_path, exist_ok=True)
        
        # Create sample template files if they don't exist
        templates = {
            'muqavile_template.docx': 'contract',
            'mezuniyyet_template.docx': 'vacation',
            'ezamiyyet_template.docx': 'business_trip',
            'memorandum_template.docx': 'memorandum',
            'telefon_kitabcasi.docx': 'contact'
        }
        
        for filename, doc_type in templates.items():
            filepath = os.path.join(self.example_docs_path, filename)
            if not os.path.exists(filepath):
                # Create a placeholder file (in real app, these would be actual templates)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"# {self.DOCUMENT_TYPES[doc_type]} Template\n")
    
    def add_document_type_column(self):
        """Add document_type column to documents table if not exists"""
        try:
            self.db_manager.execute_query(
                "ALTER TABLE documents ADD COLUMN document_type TEXT DEFAULT 'other'"
            )
        except:
            pass  # Column already exists
        
        try:
            self.db_manager.execute_query(
                "ALTER TABLE documents ADD COLUMN is_template BOOLEAN DEFAULT FALSE"
            )
        except:
            pass  # Column already exists
    
    def save_document(self, file, doc_type: str, uploaded_by: int, is_template: bool = False) -> Dict:
        """Save document with type"""
        import uuid
        from werkzeug.utils import secure_filename
        
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        file_path = os.path.join(self.config.UPLOAD_FOLDER, unique_filename)
        
        file.save(file_path)
        
        # Get file info
        file_size = os.path.getsize(file_path)
        file_ext = os.path.splitext(filename)[1].upper().replace('.', '')
        
        # Ensure columns exist
        self.add_document_type_column()
        
        # Save to database with type
        doc_id = self.db_manager.execute_query(
            """INSERT INTO documents 
               (filename, original_name, file_path, file_size, file_type, 
                uploaded_by, document_type, is_template) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (unique_filename, filename, file_path, file_size, file_ext, 
             uploaded_by, doc_type, is_template)
        )
        
        return {
            'id': doc_id,
            'name': filename,
            'type': file_ext,
            'document_type': doc_type,
            'size': file_size,
            'path': file_path,
            'is_template': is_template
        }
    
    def get_templates(self) -> List[Dict]:
        """Get all template documents"""
        try:
            templates = self.db_manager.execute_query(
                """SELECT d.*, u.username as uploaded_by_name 
                   FROM documents d 
                   JOIN users u ON d.uploaded_by = u.id 
                   WHERE d.is_template = TRUE 
                   ORDER BY d.document_type, d.created_at DESC"""
            )
            return [dict(t) for t in templates]
        except:
            return []
    
    def search_documents(self, query: str) -> List[Dict]:
        """Search documents by name or type"""
        query_lower = f"%{query.lower()}%"
        results = self.db_manager.execute_query(
            """SELECT d.*, u.username as uploaded_by_name 
               FROM documents d 
               JOIN users u ON d.uploaded_by = u.id 
               WHERE LOWER(d.original_name) LIKE ? 
                  OR LOWER(d.document_type) LIKE ?
               ORDER BY d.created_at DESC""",
            (query_lower, query_lower)
        )
        return [dict(r) for r in results]
    
    def process_contact_query(self, question: str, rag_service) -> Optional[str]:
        """Process contact/phone number queries specially"""
        contact_keywords = ['telefon', 'əlaqə', 'nömrə', 'şöbə', 'mobil', 'daxili']
        
        question_lower = question.lower()
        if not any(kw in question_lower for kw in contact_keywords):
            return None
        
        # Find contact document (telefon_kitabcasi.docx)
        contact_docs = self.db_manager.execute_query(
            """SELECT * FROM documents 
               WHERE LOWER(original_name) LIKE '%telefon%' 
                  OR LOWER(original_name) LIKE '%contact%' 
                  OR document_type = 'contact'
               LIMIT 1"""
        )
        
        if not contact_docs:
            return None
        
        contact_doc = dict(contact_docs[0])
        
        # Get answer from RAG
        result = rag_service.answer_question(question, contact_doc['id'])
        answer = result.get('answer', '')
        
        # Format as a nice table/list
        formatted_answer = self.format_contact_info(answer)
        
        return f"**📞 Əlaqə məlumatları (Mənbə: {contact_doc['original_name']})**\n\n{formatted_answer}"
    
    def format_contact_info(self, text: str) -> str:
        """Format contact information as a structured list"""
        lines = text.split('\n')
        formatted = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Check for phone patterns
            if any(word in line.lower() for word in ['tel', 'mob', 'daxili', 'phone']):
                formatted.append(f"📱 {line}")
            elif '@' in line:  # Email
                formatted.append(f"📧 {line}")
            elif any(word in line.lower() for word in ['şöbə', 'department', 'sektor']):
                formatted.append(f"🏢 {line}")
            elif any(word in line.lower() for word in ['müdir', 'rəis', 'direktor']):
                formatted.append(f"👤 **{line}**")
            else:
                formatted.append(f"• {line}")
        
        return '\n'.join(formatted) if formatted else text