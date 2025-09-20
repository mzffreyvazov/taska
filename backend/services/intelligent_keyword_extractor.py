# services/intelligent_keyword_extractor.py
"""Intelligent keyword extraction for document processing"""
import re
import json
from typing import List, Dict, Set
from collections import Counter

class IntelligentKeywordExtractor:
    """Extract meaningful keywords from documents"""
    
    def __init__(self):
        # Document type specific keywords
        self.document_type_keywords = {
            'contact': {
                'primary': ['telefon', 'mobil', 'daxili', 'email', 'elaqe', 'unvan', 'sektor', 'sobe', 'mudir'],
                'patterns': [r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', r'\b[\w\.-]+@[\w\.-]+\.\w+\b']
            },
            'contract': {
                'primary': ['muqavile', 'saziş', 'terref', 'seraitler', 'muddet', 'mebleğ', 'odenis'],
                'patterns': [r'\b\d+\s*manat\b', r'\b\d{2}\.\d{2}\.\d{4}\b']
            },
            'vacation': {
                'primary': ['mezuniyyet', 'istirahət', 'otpusk', 'gun', 'muddet', 'başlama', 'bitis'],
                'patterns': [r'\b\d+\s*gun\b', r'\b\d{2}\.\d{2}\.\d{4}\b']
            },
            'business_trip': {
                'primary': ['ezamiyyet', 'komandirovka', 'sefər', 'mekan', 'məqsəd', 'muddet'],
                'patterns': [r'\b\d+\s*gun\b', r'\b[A-ZÆÇƏÖÜŞ][a-zəçöüş]+\s+şəhər\b']
            },
            'report': {
                'primary': ['hesabat', 'melumat', 'netice', 'təhlil', 'statistika', 'gosterici'],
                'patterns': [r'\b\d+%\b', r'\b\d+\.\d+\b']
            }
        }
        
        # Important structure keywords
        self.structure_keywords = {
            'headers': ['başlıq', 'bölmə', 'hissə', 'fəsil', 'maddə'],
            'positions': ['müdir', 'rəis', 'baş', 'köməkçi', 'mütəxəssis', 'operator'],
            'departments': ['şöbə', 'sektor', 'idarə', 'bölmə', 'komitə', 'mərkəz'],
            'locations': ['otaq', 'mərtəbə', 'bina', 'ünvan', 'küçə', 'rayon']
        }
        
        # Stop words to exclude
        self.stop_words = {
            'və', 'ilə', 'üçün', 'olan', 'olur', 'edir', 'etmək', 'bu', 'o', 'bir',
            'nə', 'hansı', 'kim', 'harada', 'niyə', 'necə', 'the', 'is', 'at', 
            'which', 'on', 'and', 'a', 'an', 'as', 'are', 'də', 'da', 'ki', 
            'ya', 'yaxud', 'amma', 'lakin', 'çünki', 'həm', 'hər', 'bəzi'
        }
    
    def extract_keywords(self, text: str, doc_name: str, doc_type: str = 'other') -> List[str]:
        """Extract intelligent keywords from document"""
        keywords = set()
        text_lower = text.lower()
        
        # 1. Document name based keywords (highest priority)
        keywords.update(self._extract_from_document_name(doc_name))
        
        # 2. Special handling for contact documents
        if doc_type == 'contact' or 'telefon' in doc_name.lower() or 'contact' in doc_name.lower():
            keywords.update(self._extract_contact_specific_keywords(text, doc_name))
        else:
            # 3. Document type specific keywords for other types
            if doc_type in self.document_type_keywords:
                keywords.update(self._extract_type_specific_keywords(text_lower, doc_type))
            
            # 4. Extract headers and titles
            keywords.update(self._extract_headers_and_titles(text))
            
            # 5. Extract names and positions
            keywords.update(self._extract_names_and_positions(text))
            
            # 6. Extract departments and locations
            keywords.update(self._extract_departments_and_locations(text_lower))
            
            # 7. Extract contact information
            keywords.update(self._extract_contact_info(text))
            
            # 8. Extract important numbers and dates
            keywords.update(self._extract_numbers_and_dates(text))
            
            # 9. Extract meaningful words from content
            keywords.update(self._extract_meaningful_words(text_lower))
        
        # Filter and clean keywords
        cleaned_keywords = self._filter_and_clean_keywords(keywords)
        
        return list(cleaned_keywords)[:50]  # Limit to 50 most relevant keywords
    
    def _extract_contact_specific_keywords(self, text: str, doc_name: str) -> Set[str]:
        """Extract keywords specifically for contact/phone directory documents"""
        keywords = set()
        
        # Add document name variations
        keywords.update(self._extract_from_document_name(doc_name))
        
        # Extract person names (more selective for contacts)
        name_patterns = [
            r'\b([A-ZÆÇƏÖÜŞ][a-zəçöüşğı]+\s+[A-ZÆÇƏÖÜŞ][a-zəçöüşğı]+)\b',  # Full names
            r'\b(?:Ad|Adı|Name):\s*([A-ZÆÇƏÖÜŞ][A-Za-zəçöüşĞğıİ\s]+)',  # Name fields
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text)
            for match in matches[:15]:  # Limit to 15 names
                if isinstance(match, tuple):
                    match = match[0] if match else ""
                name_parts = match.strip().split()
                for part in name_parts:
                    if len(part) > 2 and not part.isdigit():
                        keywords.add(part.lower())
        
        # Extract department/position information
        dept_patterns = [
            r'\b(\w+)\s+şöbəsi\b',
            r'\b(\w+)\s+sektoru\b', 
            r'\b(\w+)\s+idarəsi\b',
            r'\b(\w+)\s+müdiri\b',
            r'\b(\w+)\s+rəisi\b',
        ]
        
        for pattern in dept_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:10]:
                if len(match) > 2 and not match.isdigit():
                    keywords.add(match.lower())
        
        # Extract job titles and positions
        position_keywords = [
            'müdir', 'rəis', 'müavin', 'köməkçi', 'mütəxəssis', 
            'operator', 'katib', 'məsul', 'koordinator'
        ]
        
        for keyword in position_keywords:
            if keyword in text.lower():
                keywords.add(keyword)
        
        # Extract department names
        dept_keywords = [
            'şöbə', 'sektor', 'idarə', 'bölmə', 'komitə', 'mərkəz',
            'xidmət', 'departament', 'ofis'
        ]
        
        for keyword in dept_keywords:
            if keyword in text.lower():
                keywords.add(keyword)
        
        # Extract contact-related terms
        contact_terms = [
            'telefon', 'mobil', 'daxili', 'nömrə', 'əlaqə', 
            'rabitə', 'faks', 'email'
        ]
        
        for term in contact_terms:
            if term in text.lower():
                keywords.add(term)
        
        # Extract meaningful phone numbers (avoid random digits)
        phone_patterns = [
            r'\b(050|055|051|070|077)\s*\d{7}\b',  # Mobile patterns
            r'\b\d{3}[-.]?\d{3}[-.]?\d{2,4}\b'     # General phone patterns
        ]
        
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            for match in matches[:5]:  # Limit phone numbers
                if len(match.replace('-', '').replace('.', '')) >= 7:
                    keywords.add(match.replace('-', '').replace('.', ''))
        
        # Extract office/room numbers (more selective)
        office_pattern = r'\b(?:otaq|room|office)\s*[:#-]?\s*(\d{1,3}[A-Za-z]?)\b'
        office_matches = re.findall(office_pattern, text, re.IGNORECASE)
        for match in office_matches[:3]:
            keywords.add(f"otaq_{match}")
        
        # Exclude meaningless numbers and short words
        return {kw for kw in keywords 
                if len(kw) > 2 and 
                not (kw.isdigit() and len(kw) < 3) and
                not kw in {'adı', 'və', 'ilə', 'üçün'}}
    
    
    def _extract_from_document_name(self, doc_name: str) -> Set[str]:
        """Extract keywords from document name"""
        keywords = set()
        
        # Clean document name
        name_clean = doc_name.lower().replace('.docx', '').replace('.pdf', '').replace('.xlsx', '')
        name_clean = re.sub(r'[^\w\s]', ' ', name_clean)
        
        # Add full name
        keywords.add(name_clean)
        
        # Add individual words
        words = name_clean.split()
        for word in words:
            if len(word) > 2 and word not in self.stop_words:
                keywords.add(word)
        
        # Add variations
        keywords.add(name_clean.replace('_', ' '))
        keywords.add(name_clean.replace('-', ' '))
        
        return keywords
    
    def _extract_type_specific_keywords(self, text: str, doc_type: str) -> Set[str]:
        """Extract keywords specific to document type"""
        keywords = set()
        type_config = self.document_type_keywords[doc_type]
        
        # Add primary keywords if found in text
        for keyword in type_config['primary']:
            if keyword in text:
                keywords.add(keyword)
        
        # Extract pattern-based keywords
        for pattern in type_config['patterns']:
            matches = re.findall(pattern, text)
            keywords.update([match.strip() for match in matches[:5]])  # Limit matches
        
        return keywords
    
    def _extract_headers_and_titles(self, text: str) -> Set[str]:
        """Extract headers and titles from text"""
        keywords = set()
        
        # Headers with special formatting
        header_patterns = [
            r'^([A-ZÆÇƏÖÜŞ][A-Za-zəçöüşĞğıİ\s]+)$',  # All caps lines
            r'^(\d+\.\s*[A-ZÆÇƏÖÜŞ][A-Za-zəçöüşĞğıİ\s]+)',  # Numbered headers
            r'^([A-ZÆÇƏÖÜŞ][A-Za-zəçöüşĞğıİ\s]+):',  # Headers with colon
            r'===\s*([^=]+)\s*===',  # Text between === markers
        ]
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line or len(line) < 5 or len(line) > 100:
                continue
            
            for pattern in header_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    header = match.group(1).strip()
                    # Clean and add header words
                    header_words = re.findall(r'\b[A-Za-zəçöüşĞğıİ]+\b', header.lower())
                    for word in header_words:
                        if len(word) > 2 and word not in self.stop_words:
                            keywords.add(word)
                    break
        
        return keywords
    
    def _extract_names_and_positions(self, text: str) -> Set[str]:
        """Extract person names and job positions"""
        keywords = set()
        
        # Name patterns (Azerbaijani names)
        name_patterns = [
            r'\b[A-ZÆÇƏÖÜŞ][a-zəçöüşğı]+\s+[A-ZÆÇƏÖÜŞ][a-zəçöüşğı]+(?:\s+[A-ZÆÇƏÖÜŞ][a-zəçöüşğı]+)?\b',
            r'\b(?:Ad|Adı|Soyad|Soyadı):\s*([A-ZÆÇƏÖÜŞ][A-Za-zəçöüşĞğıİ\s]+)',
        ]
        
        for pattern in name_patterns:
            matches = re.findall(pattern, text)
            for match in matches[:10]:  # Limit to 10 names
                if isinstance(match, tuple):
                    match = match[0] if match else ""
                name_words = match.strip().split()
                for word in name_words:
                    if len(word) > 2:
                        keywords.add(word.lower())
        
        # Position keywords
        for category, terms in self.structure_keywords.items():
            if category == 'positions':
                for term in terms:
                    if term in text.lower():
                        keywords.add(term)
        
        return keywords
    
    def _extract_departments_and_locations(self, text: str) -> Set[str]:
        """Extract department and location information"""
        keywords = set()
        
        # Department patterns
        dept_patterns = [
            r'\b(\w+)\s+şöbəsi\b',
            r'\b(\w+)\s+sektoru\b',
            r'\b(\w+)\s+idarəsi\b',
            r'şöbə\s*:\s*(\w+)',
            r'sektor\s*:\s*(\w+)',
        ]
        
        for pattern in dept_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:5]:
                if len(match) > 2 and match not in self.stop_words:
                    keywords.add(match.lower())
        
        # Location keywords
        location_keywords = self.structure_keywords['locations']
        for keyword in location_keywords:
            if keyword in text:
                keywords.add(keyword)
        
        return keywords
    
    def _extract_contact_info(self, text: str) -> Set[str]:
        """Extract contact information"""
        keywords = set()
        
        # Phone numbers
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{2,4}\b'
        phones = re.findall(phone_pattern, text)
        for phone in phones[:5]:
            keywords.add(phone.replace('-', '').replace('.', ''))
        
        # Email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        for email in emails[:5]:
            # Add domain and username
            if '@' in email:
                username, domain = email.split('@', 1)
                keywords.add(username.lower())
                keywords.add(domain.lower())
        
        return keywords
    
    def _extract_numbers_and_dates(self, text: str) -> Set[str]:
        """Extract important numbers and dates"""
        keywords = set()
        
        # Dates in various formats
        date_patterns = [
            r'\b\d{1,2}\.\d{1,2}\.\d{4}\b',  # DD.MM.YYYY
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',   # DD/MM/YYYY
            r'\b\d{4}-\d{1,2}-\d{1,2}\b',   # YYYY-MM-DD
        ]
        
        for pattern in date_patterns:
            dates = re.findall(pattern, text)
            for date in dates[:3]:  # Limit to 3 dates
                keywords.add(date)
        
        # Important numbers with context
        number_patterns = [
            r'\b(\d+)\s*manat\b',
            r'\b(\d+)\s*gün\b', 
            r'\b(\d+)\s*saat\b',
            r'\b(\d+)%\b',
        ]
        
        for pattern in number_patterns:
            numbers = re.findall(pattern, text.lower())
            for num in numbers[:3]:
                keywords.add(num)
        
        return keywords
    
    def _extract_meaningful_words(self, text: str) -> Set[str]:
        """Extract meaningful words from text content"""
        keywords = set()
        
        # Extract all words
        words = re.findall(r'\b[a-zA-Zəçöüşğı]{3,}\b', text.lower())
        
        # Count frequency
        word_freq = Counter(words)
        
        # Get most frequent words (excluding stop words)
        for word, freq in word_freq.most_common(20):
            if word not in self.stop_words and freq > 1:
                keywords.add(word)
        
        # Add words that appear with important context
        context_patterns = [
            r'məsul\s+(\w+)',
            r'(\w+)\s+məsuldur',
            r'təyin\s+edilir\s+(\w+)',
            r'(\w+)\s+tərəfindən',
        ]
        
        for pattern in context_patterns:
            matches = re.findall(pattern, text)
            for match in matches[:3]:
                if len(match) > 2 and match not in self.stop_words:
                    keywords.add(match)
        
        return keywords
    
    def _filter_and_clean_keywords(self, keywords: Set[str]) -> List[str]:
        """Filter and clean keywords with enhanced contact document handling"""
        filtered = []
        
        # Enhanced stop words for contact documents
        extended_stop_words = self.stop_words.union({
            'adı', 'soyadı', 'vəzifəsi', 'cədvəl', 'siyahı', 'nömrə',
            'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
            'iyul', 'avqust', 'sentyabr', 'oktyabr', 'noyabr', 'dekabr',
            '2023', '2024', '2025', 'tarix', 'sənəd'
        })
        
        for keyword in keywords:
            keyword = str(keyword).strip().lower()
            
            # Skip if too short or too long
            if len(keyword) < 2 or len(keyword) > 30:
                continue
            
            # Skip extended stop words
            if keyword in extended_stop_words:
                continue
            
            # Skip pure numbers unless they're meaningful (phone numbers, room numbers)
            if keyword.isdigit():
                if len(keyword) < 3 or len(keyword) > 10:
                    continue
                # Keep only meaningful numbers (phone patterns, room numbers)
                if not (keyword.startswith(('050', '055', '051', '070', '077')) or
                       (len(keyword) >= 7 and len(keyword) <= 10)):
                    continue
            
            # Skip meaningless patterns
            if re.match(r'^[^\w]*$', keyword):  # Only special characters
                continue
            
            # Skip very short numeric combinations
            if len(keyword) <= 3 and any(c.isdigit() for c in keyword):
                continue
            
            # Keep meaningful content
            filtered.append(keyword)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_keywords = []
        for kw in filtered:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)
        
        # Prioritize meaningful keywords for contact documents
        prioritized = []
        contact_priority_words = [
            'telefon', 'mobil', 'daxili', 'nömrə', 'müdir', 'rəis', 
            'şöbə', 'sektor', 'idarə', 'məsul', 'köməkçi'
        ]
        
        # Add priority words first
        for kw in unique_keywords:
            if any(priority in kw for priority in contact_priority_words):
                prioritized.append(kw)
        
        # Add names (capitalized words that are not in stop words)
        for kw in unique_keywords:
            if (kw not in prioritized and 
                len(kw) > 3 and 
                not kw.isdigit() and
                any(c.isupper() for c in kw.title())):
                prioritized.append(kw)
        
        # Add remaining meaningful keywords
        for kw in unique_keywords:
            if kw not in prioritized and len(kw) > 3:
                prioritized.append(kw)
        
        return prioritized[:40]  # Limit to 40 most relevant keywords