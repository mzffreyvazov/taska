#!/usr/bin/env python3
"""Test script for template search functionality"""

import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(__file__))

def test_template_search():
    """Test the template search logic"""
    
    # Mock template documents
    mock_templates = [
        {
            'id': 1,
            'original_name': 'mezuniyyet_template.docx',
            'document_type': 'vacation',
            'is_template': True,
            'file_type': 'DOCX',
            'file_size': 25600
        },
        {
            'id': 2,
            'original_name': 'muqavile_template.docx',
            'document_type': 'contract',
            'is_template': True,
            'file_type': 'DOCX',
            'file_size': 30720
        },
        {
            'id': 3,
            'original_name': 'ezamiyyet_template.docx',
            'document_type': 'business_trip',
            'is_template': True,
            'file_type': 'DOCX',
            'file_size': 28160
        },
        {
            'id': 4,
            'original_name': 'memorandum_template.docx',
            'document_type': 'memorandum',
            'is_template': True,
            'file_type': 'DOCX',
            'file_size': 32768
        }
    ]
    
    def find_template_by_name(question_text, templates):
        """Find template by intelligent name matching"""
        question_lower = question_text.lower()
        
        # Enhanced template keywords mapping
        template_keywords = {
            'məzuniyyət': ['vacation', 'mezuniyyet', 'məzuniyyət'],
            'mezuniyyet': ['vacation', 'mezuniyyet', 'məzuniyyət'],
            'vacation': ['vacation', 'mezuniyyet', 'məzuniyyət'],
            'ezamiyyət': ['business_trip', 'ezamiyyet', 'ezamiyyət'],
            'ezamiyyet': ['business_trip', 'ezamiyyet', 'ezamiyyət'],
            'business_trip': ['business_trip', 'ezamiyyet', 'ezamiyyət'],
            'müqavilə': ['contract', 'muqavile', 'müqavilə'],
            'muqavile': ['contract', 'muqavile', 'müqavilə'],
            'contract': ['contract', 'muqavile', 'müqavilə'],
            'memorandum': ['memorandum'],
            'telefon': ['phone_book', 'telefon', 'kitabça'],
            'kitabça': ['phone_book', 'telefon', 'kitabça'],
            'kitabcası': ['phone_book', 'telefon', 'kitabça']
        }
        
        # First try exact keyword matching
        for keyword, doc_types in template_keywords.items():
            if keyword in question_lower:
                for doc_type in doc_types:
                    template_doc = next((d for d in templates if d.get('document_type') == doc_type), None)
                    if template_doc:
                        return template_doc
        
        # If no exact match, try filename matching
        for template in templates:
            template_name_lower = template['original_name'].lower()
            # Remove file extension for comparison
            template_base_name = os.path.splitext(template_name_lower)[0]
            
            # Check if any word from the question matches the template name
            question_words = question_lower.split()
            for word in question_words:
                if len(word) > 2 and word in template_base_name:
                    return template
                
            # Also check if template name words are in question
            template_words = template_base_name.replace('_', ' ').split()
            for word in template_words:
                if len(word) > 2 and word in question_lower:
                    return template
        
        return None
    
    # Test cases
    test_cases = [
        "Məzuniyyət şablonu lazımdır",
        "Müqavilə şablonu yükləməyə ehtiyacım var",
        "Ezamiyyət nümunəsi göstər",
        "Memorandum template download et",
        "mezuniyyet şablonu",
        "muqavile nümunəsi",
        "vacation template",
        "contract şablonu",
        "Şablon lazımdır", # Should show all templates
        "Template yüklə", # Should show all templates
    ]
    
    print("=== Template Search Test Results ===\n")
    
    for i, question in enumerate(test_cases, 1):
        print(f"{i}. Question: '{question}'")
        
        # Check if it's a template request
        template_indicators = ['şablon', 'shablon', 'nümunə', 'numune', 'template', 'yüklə', 'yukle', 'download', 'link']
        is_template_request = any(indicator in question.lower() for indicator in template_indicators)
        
        if is_template_request:
            result = find_template_by_name(question, mock_templates)
            if result:
                print(f"   ✅ Found: {result['original_name']} (type: {result['document_type']})")
            else:
                print(f"   ❓ No specific template found - would show all templates")
        else:
            print(f"   ❌ Not recognized as template request")
        
        print()

if __name__ == "__main__":
    test_template_search()
