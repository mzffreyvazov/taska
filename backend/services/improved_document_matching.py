# services/improved_document_matching.py
"""Improved document matching system for better document selection"""
import re
import json
from typing import Optional, List, Dict, Tuple
from collections import Counter

class ImprovedDocumentMatcher:
    """Advanced document matching with multiple strategies"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        
        # Document type keywords for better matching
        self.doc_type_keywords = {
            'contact': ['telefon', 'əlaqə', 'nömrə', 'mobil', 'daxili', 'şöbə', 'müdir', 'işçi', 'kim'],
            'contract': ['müqavilə', 'razılaşma', 'saziş', 'şərt', 'müddət', 'məbləğ', 'tərəf'],
            'vacation': ['məzuniyyət', 'istirahət', 'təitl', 'günlük', 'ödənişli', 'ödənişsiz'],
            'business_trip': ['ezamiyyət', 'səfər', 'komandirovka', 'məkan', 'müddət'],
            'memorandum': ['memorandum', 'anlaşma', 'razılaşma', 'protokol'],
            'report': ['hesabat', 'təhlil', 'statistika', 'məlumat', 'nəticə'],
            'letter': ['məktub', 'müraciət', 'ərizə', 'xahiş'],
            'invoice': ['qaimə', 'faktura', 'ödəniş', 'məbləğ']
        }
        
        # Common question patterns
        self.question_patterns = {
            'who': r'\b(kim|kimin|kimdir|kimlər)\b',
            'what': r'\b(nə|nədir|nələr|hansı|hansılar)\b',
            'where': r'\b(hara|harada|haradan|haraya)\b',
            'when': r'\b(nə vaxt|nə zaman|haçan|tarix)\b',
            'phone': r'\b(telefon|nömrə|mobil|daxili|zəng|çağır)\b',
            'document': r'\b(sənəd|fayl|document|file)\b'
        }
    
    def enhanced_document_matching(self, question: str, documents: List[Dict]) -> Optional[int]:
        """Enhanced document matching with multiple strategies"""
        
        if not documents:
            return None
        
        print(f"\n=== Enhanced Document Matching ===")
        print(f"Question: '{question}'")
        print(f"Available documents: {len(documents)}")
        
        # Strategy 1: Direct name match
        doc_id = self._match_by_document_name(question, documents)
        if doc_id:
            print(f"✓ Strategy 1 (Name Match) succeeded: Document ID {doc_id}")
            return doc_id
        
        # Strategy 2: Keyword-based matching
        doc_id = self._match_by_keywords(question, documents)
        if doc_id:
            print(f"✓ Strategy 2 (Keyword Match) succeeded: Document ID {doc_id}")
            return doc_id
        
        # Strategy 3: Document type inference
        doc_id = self._match_by_document_type(question, documents)
        if doc_id:
            print(f"✓ Strategy 3 (Type Match) succeeded: Document ID {doc_id}")
            return doc_id
        
        # Strategy 4: Smart contextual matching
        doc_id = self._match_by_context(question, documents)
        if doc_id:
            print(f"✓ Strategy 4 (Context Match) succeeded: Document ID {doc_id}")
            return doc_id
        
        print("✗ No suitable document found")
        return None
    
    def _match_by_document_name(self, question: str, documents: List[Dict]) -> Optional[int]:
        """Match by document name mentioned in question"""
        question_lower = question.lower()
        
        for doc in documents:
            doc_name = doc['original_name'].lower()
            doc_name_clean = re.sub(r'[_\-\.]', ' ', doc_name).lower()
            
            # Check various forms of the document name
            if (doc_name in question_lower or 
                doc_name_clean in question_lower or
                doc_name.replace('.docx', '') in question_lower or
                doc_name.replace('.pdf', '') in question_lower):
                return doc['id']
        
        return None
    
    def _match_by_keywords(self, question: str, documents: List[Dict]) -> Optional[int]:
        """Match by extracted keywords"""
        question_lower = question.lower()
        question_words = set(re.findall(r'\b[a-zəçöüşğıА-Яа-я]+\b', question_lower))
        
        best_match = None
        best_score = 0
        
        for doc in documents:
            if not doc.get('keywords'):
                continue
            
            try:
                doc_keywords = json.loads(doc['keywords'])
                doc_keywords_lower = [kw.lower() for kw in doc_keywords]
                
                # Calculate matching score
                score = 0
                for q_word in question_words:
                    if len(q_word) < 3:  # Skip very short words
                        continue
                    
                    # Exact match
                    if q_word in doc_keywords_lower:
                        score += 3
                    # Partial match
                    else:
                        for doc_kw in doc_keywords_lower:
                            if q_word in doc_kw or doc_kw in q_word:
                                score += 1
                                break
                
                # Bonus for document type match
                doc_type = doc.get('document_type', 'other')
                if doc_type in self.doc_type_keywords:
                    type_keywords = self.doc_type_keywords[doc_type]
                    for type_kw in type_keywords:
                        if type_kw in question_lower:
                            score += 2
                
                if score > best_score:
                    best_score = score
                    best_match = doc['id']
                    
            except (json.JSONDecodeError, TypeError):
                continue
        
        # Return if score is significant enough
        if best_score >= 3:
            return best_match
        
        return None
    
    def _match_by_document_type(self, question: str, documents: List[Dict]) -> Optional[int]:
        """Match by inferred document type"""
        question_lower = question.lower()
        
        # Detect document type from question
        detected_types = []
        for doc_type, keywords in self.doc_type_keywords.items():
            type_score = sum(1 for kw in keywords if kw in question_lower)
            if type_score > 0:
                detected_types.append((doc_type, type_score))
        
        if not detected_types:
            return None
        
        # Sort by score and get best type
        detected_types.sort(key=lambda x: x[1], reverse=True)
        best_type = detected_types[0][0]
        
        # Find documents of this type
        matching_docs = [
            doc for doc in documents 
            if doc.get('document_type') == best_type
        ]
        
        if matching_docs:
            # Return the most recently processed document of this type
            matching_docs.sort(
                key=lambda x: (x.get('is_processed', False), x.get('created_at', '')),
                reverse=True
            )
            return matching_docs[0]['id']
        
        return None
    
    def _match_by_context(self, question: str, documents: List[Dict]) -> Optional[int]:
        """Smart contextual matching based on question patterns"""
        question_lower = question.lower()
        
        # Detect question type
        is_phone_query = bool(re.search(self.question_patterns['phone'], question_lower))
        is_who_query = bool(re.search(self.question_patterns['who'], question_lower))
        
        # Special handling for contact queries
        if is_phone_query or (is_who_query and any(word in question_lower for word in ['telefon', 'nömrə', 'əlaqə'])):
            # Look for contact document
            for doc in documents:
                doc_name_lower = doc['original_name'].lower()
                doc_type = doc.get('document_type', '')
                
                if (doc_type == 'contact' or 
                    'telefon' in doc_name_lower or 
                    'contact' in doc_name_lower or
                    'əlaqə' in doc_name_lower):
                    return doc['id']
        
        # Extract person names from question
        person_names = re.findall(
            r'\b[A-ZƏÇĞÖÜŞİ][a-zəçöüşğı]+\s+[A-ZƏÇĞÖÜŞİ][a-zəçöüşğı]+\b',
            question
        )
        
        if person_names:
            # Search for documents containing these names
            for doc in documents:
                if not doc.get('keywords'):
                    continue
                
                try:
                    doc_keywords = json.loads(doc['keywords'])
                    doc_keywords_lower = [kw.lower() for kw in doc_keywords]
                    
                    for name in person_names:
                        name_parts = name.lower().split()
                        if any(part in doc_keywords_lower for part in name_parts):
                            return doc['id']
                            
                except (json.JSONDecodeError, TypeError):
                    continue
        
        return None
    
    def smart_document_search(self, question: str) -> Optional[int]:
        """Smart search across all documents"""
        try:
            # Get all processed documents
            documents = self.db_manager.execute_query(
                """SELECT id, original_name, document_type, keywords, is_processed, created_at
                   FROM documents 
                   WHERE is_processed = TRUE
                   ORDER BY created_at DESC"""
            )
            
            if not documents:
                print("No processed documents found")
                return None
            
            # Convert to list of dicts
            docs_list = []
            for doc in documents:
                doc_dict = dict(doc)
                docs_list.append(doc_dict)
            
            # Use enhanced matching
            return self.enhanced_document_matching(question, docs_list)
            
        except Exception as e:
            print(f"Smart document search error: {e}")
            return None
    
    def calculate_relevance_scores(self, question: str, documents: List[Dict]) -> List[Tuple[int, float]]:
        """Calculate relevance scores for all documents"""
        question_lower = question.lower()
        question_words = set(re.findall(r'\b[a-zəçöüşğıА-Яа-я]+\b', question_lower))
        
        scores = []
        
        for doc in documents:
            score = 0.0
            
            # Name match score
            doc_name_lower = doc['original_name'].lower()
            if any(word in doc_name_lower for word in question_words if len(word) > 3):
                score += 5
            
            # Keyword match score
            if doc.get('keywords'):
                try:
                    doc_keywords = json.loads(doc['keywords'])
                    doc_keywords_lower = [kw.lower() for kw in doc_keywords]
                    
                    for q_word in question_words:
                        if len(q_word) < 3:
                            continue
                        
                        if q_word in doc_keywords_lower:
                            score += 3
                        else:
                            for doc_kw in doc_keywords_lower:
                                if q_word in doc_kw or doc_kw in q_word:
                                    score += 1
                                    break
                                    
                except (json.JSONDecodeError, TypeError):
                    pass
            
            # Document type score
            doc_type = doc.get('document_type', 'other')
            if doc_type in self.doc_type_keywords:
                type_keywords = self.doc_type_keywords[doc_type]
                type_score = sum(1 for kw in type_keywords if kw in question_lower)
                score += type_score * 2
            
            # Processing status bonus
            if doc.get('is_processed'):
                score += 1
            
            scores.append((doc['id'], score))
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores
    
    def get_document_suggestions(self, question: str, limit: int = 3) -> List[Dict]:
        """Get top document suggestions for a question"""
        try:
            documents = self.db_manager.execute_query(
                """SELECT id, original_name, document_type, keywords, is_processed
                   FROM documents 
                   WHERE is_processed = TRUE"""
            )
            
            if not documents:
                return []
            
            docs_list = [dict(doc) for doc in documents]
            scores = self.calculate_relevance_scores(question, docs_list)
            
            suggestions = []
            for doc_id, score in scores[:limit]:
                if score > 0:
                    doc = next((d for d in docs_list if d['id'] == doc_id), None)
                    if doc:
                        suggestions.append({
                            'id': doc['id'],
                            'name': doc['original_name'],
                            'type': doc.get('document_type', 'other'),
                            'relevance_score': score
                        })
            
            return suggestions
            
        except Exception as e:
            print(f"Document suggestions error: {e}")
            return []