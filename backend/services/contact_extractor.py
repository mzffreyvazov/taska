# services/contact_extractor.py
"""DOCX sənədlərindən əlaqə məlumatlarını çıxarmaq üçün modul"""
import docx
import re
from typing import List, Dict, Optional

class ContactExtractor:
    """DOCX sənədlərindən kontakt siyahısını çıxarır"""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.contacts = []
        self._extract_contacts()
    
    def _extract_contacts(self):
        """DOCX sənədini oxu və kontaktları çıxar"""
        try:
            doc = docx.Document(self.file_path)
        except Exception as e:
            print(f"Sənəd açıla bilmədi: {e}")
            return
        
        for table in doc.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if len(cells) < 3:
                    continue
                
                name = self._find_name(cells)
                if not name or not self._is_valid_name(name):
                    continue
                
                contact = {
                    "name": name,
                    "position": self._find_position(cells),
                    "phone_direct": self._find_direct_phone(cells),
                    "phone_city": self._find_city_phone(cells),
                    "phone_mobile": self._find_mobile_phone(cells),
                    "email": self._find_email(cells)
                }
                
                if any(contact.values()):
                    self.contacts.append(contact)
    
    def _find_name(self, cells: List[str]) -> Optional[str]:
        """Ad-soyadı sütunlardan tap"""
        name_patterns = [
            r'\b[A-ZƏÇĞÖÜŞİ][a-zəçöüşğı]+\s+[A-ZƏÇĞÖÜŞİ][a-zəçöüşğı]+\b',
            r'\b[A-ZƏÇĞÖÜŞİ][a-zəçöüşğı]+\s+[A-ZƏÇĞÖÜŞİ][a-zəçöüşğı]+\s+[A-ZƏÇĞÖÜŞİ][a-zəçöüşğı]+\b'
        ]
        for cell in cells:
            for pattern in name_patterns:
                match = re.search(pattern, cell)
                if match:
                    return match.group()
        return None
    
    def _is_valid_name(self, text: str) -> bool:
        """Mətn şəxsin adı ola bilərmi?"""
        return bool(re.search(r'[A-ZƏÇĞÖÜŞİ][a-zəçöüşğı]+\s+[A-ZƏÇĞÖÜŞİ][a-zəçöüşğı]+', text))
    
    def _find_position(self, cells: List[str]) -> Optional[str]:
        """Vəzifəni tap"""
        position_keywords = ['müdir', 'rəis', 'koordinator', 'mütəxəssis', 'konsultant', 'direktor', 'katib']
        for cell in cells:
            if any(kw in cell.lower() for kw in position_keywords) and len(cell) < 100:
                return cell
        return None
    
    def _find_direct_phone(self, cells: List[str]) -> Optional[str]:
        """Daxili nömrəni tap"""
        for cell in cells:
            if re.match(r'^\d{2,4}$', cell):
                return cell
        return None
    
    def _find_city_phone(self, cells: List[str]) -> Optional[str]:
        """Şəhər nömrəsini tap"""
        for cell in cells:
            if re.match(r'^\d{3}[-.]?\d{2}[-.]?\d{2}$', cell):
                return cell
        return None
    
    def _find_mobile_phone(self, cells: List[str]) -> Optional[str]:
        """Mobil nömrəni tap"""
        mobile_patterns = [
            r'(\+994|05[0157]|5[0157]|7[07])\D*\d{2}\D*\d{2}\D*\d{2}',
            r'\d{3}[-.]?\d{3}[-.]?\d{2,4}'
        ]
        for cell in cells:
            for pattern in mobile_patterns:
                match = re.search(pattern, cell)
                if match:
                    return match.group().replace(' ', '').replace('-', '')
        return None
    
    def _find_email(self, cells: List[str]) -> Optional[str]:
        """Email adresini tap"""
        for cell in cells:
            if re.search(r'@', cell) and re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', cell):
                return cell
        return None
    
    def get_contacts(self) -> List[Dict]:
        """Bütün kontaktları qaytar"""
        return self.contacts
    
    def search_by_name(self, query: str) -> List[Dict]:
        """Ad-soyad əsasında axtarış"""
        query = query.strip().lower()
        if not query:
            return []
        
        results = []
        for contact in self.contacts:
            full_name = contact["name"].lower()
            if all(part.lower() in full_name for part in query.split() if len(part) > 2):
                results.append(contact)
        
        return results