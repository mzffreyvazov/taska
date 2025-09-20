# services/contact_service.py
"""Service for handling contact/phone queries"""
import re
import json
from typing import Optional, List, Dict

class ContactService:
    """Handle contact and phone number queries"""
    
    CONTACT_KEYWORDS = ['telefon', 'əlaqə', 'nömrə', 'şöbə', 'mobil', 'daxili', 'tel', 'phone']
    
    def __init__(self, db_manager, rag_service):
        self.db_manager = db_manager
        self.rag_service = rag_service
    
    def is_contact_query(self, question: str) -> bool:
        """Check if query is about contact information"""
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in self.CONTACT_KEYWORDS)
    
    def find_contact_document(self) -> Optional[Dict]:
        """Find the contact document (telefon_kitabcasi.docx)"""
        docs = self.db_manager.execute_query(
            """SELECT * FROM documents 
               WHERE LOWER(original_name) LIKE '%telefon%' 
                  OR LOWER(original_name) LIKE '%contact%' 
                  OR LOWER(original_name) LIKE '%əlaqə%'
                  OR document_type = 'contact'
               LIMIT 1"""
        )
        
        if docs:
            return dict(docs[0])
        return None
    
    def process_contact_query(self, question: str) -> Optional[Dict]:
        """Process contact query and return formatted response"""
        
        # Find contact document
        contact_doc = self.find_contact_document()
        if not contact_doc:
            return {
                'success': False,
                'answer': 'Telefon kitabçası tapılmadı. Zəhmət olmasa admin ilə əlaqə saxlayın.',
                'type': 'no_contact_document'
            }
        
        # Check if document is processed
        if not contact_doc.get('is_processed'):
            return {
                'success': False,
                'answer': 'Telefon kitabçası hələ işlənməyib. Zəhmət olmasa bir az gözləyin.',
                'type': 'document_not_processed'
            }
        
        # Get answer from RAG - search for ALL matching people
        result = self.rag_service.answer_question(question, contact_doc['id'])
        
        if not result.get('success'):
            return {
                'success': False,
                'answer': 'Məlumat tapılmadı.',
                'type': 'no_results'
            }
        
        # Format the answer
        formatted_answer = self.format_contact_answer(result['answer'], question)
        
        return {
            'success': True,
            'answer': formatted_answer,
            'source': contact_doc['original_name'],
            'type': 'contact_answer'
        }
    
    def format_contact_answer(self, raw_answer: str, question: str) -> str:
        """Format contact information in a structured way"""
        lines = raw_answer.split('\n')
        contacts = []
        current_contact = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_contact:
                    contacts.append(current_contact)
                    current_contact = {}
                continue
            
            # Parse different types of information
            if any(x in line.lower() for x in ['ad:', 'adı:', 'name:', 'soyadı:']):
                current_contact['name'] = line.split(':', 1)[1].strip() if ':' in line else line
            elif any(x in line.lower() for x in ['vəzifə:', 'position:', 'title:']):
                current_contact['position'] = line.split(':', 1)[1].strip() if ':' in line else line
            elif any(x in line.lower() for x in ['şöbə:', 'department:', 'bölmə:']):
                current_contact['department'] = line.split(':', 1)[1].strip() if ':' in line else line
            elif any(x in line.lower() for x in ['mobil:', 'mobile:', 'cib:']):
                current_contact['mobile'] = line.split(':', 1)[1].strip() if ':' in line else line
            elif any(x in line.lower() for x in ['daxili:', 'extension:', 'ext:']):
                current_contact['extension'] = line.split(':', 1)[1].strip() if ':' in line else line
            elif any(x in line.lower() for x in ['tel:', 'telefon:', 'phone:']):
                current_contact['phone'] = line.split(':', 1)[1].strip() if ':' in line else line
            elif '@' in line:
                current_contact['email'] = line
            else:
                # Try to detect phone numbers
                phone_match = re.search(r'\d{3}[-.]?\d{3}[-.]?\d{2,4}', line)
                if phone_match:
                    if 'phone' not in current_contact:
                        current_contact['phone'] = phone_match.group()
        
        # Add last contact if exists
        if current_contact:
            contacts.append(current_contact)
        
        # If no structured data found, return original with formatting
        if not contacts:
            return f"📞 **Əlaqə Məlumatları**\n\n{raw_answer}"
        
        # Format contacts nicely
        formatted = "📞 **Əlaqə Məlumatları**\n\n"
        
        if len(contacts) > 1:
            formatted += f"*{len(contacts)} nəfər tapıldı:*\n\n"
        
        for i, contact in enumerate(contacts, 1):
            if len(contacts) > 1:
                formatted += f"**{i}. "
            
            if 'name' in contact:
                formatted += f"👤 **{contact['name']}**\n"
            
            if 'position' in contact:
                formatted += f"   💼 Vəzifə: {contact['position']}\n"
            
            if 'department' in contact:
                formatted += f"   🏢 Şöbə: {contact['department']}\n"
            
            if 'phone' in contact:
                formatted += f"   ☎️ Telefon: {contact['phone']}\n"
            
            if 'mobile' in contact:
                formatted += f"   📱 Mobil: {contact['mobile']}\n"
            
            if 'extension' in contact:
                formatted += f"   📞 Daxili: {contact['extension']}\n"
            
            if 'email' in contact:
                formatted += f"   📧 Email: {contact['email']}\n"
            
            formatted += "\n"
        
        return formatted.strip()