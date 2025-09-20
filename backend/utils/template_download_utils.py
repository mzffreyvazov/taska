# backend/utils/template_download_utils.py
"""Template download utilities for enhanced functionality"""
import os
import json
from typing import Dict, List, Optional
from flask import current_app, send_file, jsonify

class TemplateDownloadManager:
    """Manage template downloads and metadata"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Template metadata
        self.template_metadata = {
            'vacation': {
                'az_name': 'Məzuniyyət Ərizəsi',
                'description': 'Məzuniyyət üçün rəsmi ərizə forması',
                'file_pattern': ['mezuniyyet', 'vacation', 'tetil'],
                'required_fields': ['başlama_tarixi', 'bitiş_tarixi', 'səbəb'],
                'instructions': {
                    'az': 'Bu formu doldurub rəhbərinizə təqdim edin',
                    'en': 'Fill this form and submit to your supervisor'
                }
            },
            'business_trip': {
                'az_name': 'Ezamiyyət Ərizəsi', 
                'description': 'Ezamiyyət üçün rəsmi ərizə forması',
                'file_pattern': ['ezamiyyet', 'business_trip', 'komandirovka'],
                'required_fields': ['məqsəd', 'məkan', 'müddət'],
                'instructions': {
                    'az': 'Ezamiyyət məqsədini və müddətini dəqiq qeyd edin',
                    'en': 'Specify the purpose and duration of business trip'
                }
            },
            'contract': {
                'az_name': 'Müqavilə Şablonu',
                'description': 'Ümumi müqavilə şablonu',
                'file_pattern': ['muqavile', 'contract', 'razilashma'],
                'required_fields': ['tərəflər', 'məbləğ', 'şərtlər'],
                'instructions': {
                    'az': 'Müqavilə şərtlərini diqqətlə doldurub hüquqi şöbə ilə razılaşdırın',
                    'en': 'Fill contract terms carefully and coordinate with legal department'
                }
            },
            'memorandum': {
                'az_name': 'Anlaşma Memorandumu',
                'description': 'Rəsmi anlaşma memorandumu şablonu', 
                'file_pattern': ['memorandum', 'anlashma', 'razilashma'],
                'required_fields': ['məqsəd', 'tərəflər', 'şərtlər'],
                'instructions': {
                    'az': 'Anlaşma şərtlərini aydın və dəqiq qeyd edin',
                    'en': 'State agreement terms clearly and precisely'
                }
            }
        }
    
    def find_template_by_type(self, template_type: str) -> Optional[Dict]:
        """Find template document by type"""
        documents = self.db_manager.get_documents()
        
        for doc in documents:
            if (doc.get('is_template') and 
                doc.get('document_type') == template_type):
                return doc
        
        return None
    
    def find_template_by_keywords(self, keywords: List[str]) -> Optional[Dict]:
        """Find template by matching keywords"""
        documents = self.db_manager.get_documents()
        
        for template_type, metadata in self.template_metadata.items():
            # Check if keywords match template patterns
            if any(kw in metadata['file_pattern'] for kw in keywords):
                # Find corresponding document
                template_doc = self.find_template_by_type(template_type)
                if template_doc:
                    return {
                        'document': template_doc,
                        'metadata': metadata,
                        'type': template_type
                    }
        
        return None
    
    def get_template_download_response(self, template_match: Dict, base_url: str = "http://localhost:5000") -> Dict:
        """Generate template download response with metadata"""
        document = template_match['document']
        metadata = template_match['metadata']
        template_type = template_match['type']
        
        download_url = f"{base_url}/api/documents/{document['id']}/download"
        
        response = {
            'template_name': metadata['az_name'],
            'description': metadata['description'],
            'download_url': download_url,
            'file_info': {
                'name': document['original_name'],
                'size': document['file_size'],
                'type': document['file_type']
            },
            'instructions': metadata['instructions']['az'],
            'required_fields': metadata['required_fields']
        }
        
        return response
    
    def create_template_response_text(self, template_response: Dict) -> str:
        """Create formatted response text for template download"""
        
        text = f"""**{template_response['template_name']}** tapıldı!

📋 **Təsvir:** {template_response['description']}

📥 **Yükləmə linki:** [Bu linkə klikləyin]({template_response['download_url']})

📄 **Fayl məlumatları:**
- Fayl adı: {template_response['file_info']['name']}
- Fayl tipi: {template_response['file_info']['type']}
- Fayl ölçüsü: {template_response['file_info']['size']} bayt

📝 **İstifadə təlimatı:** {template_response['instructions']}

✅ **Vacib sahələr:**"""
        
        for field in template_response['required_fields']:
            text += f"\n- {field}"
        
        text += "\n\nLinkə klikləyərək şablonu kompüterinizə yükləyə bilərsiniz."
        
        return text
