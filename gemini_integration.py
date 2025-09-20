# improved_gemini_integration.py
import google.generativeai as genai
from typing import List, Dict, Any, Optional, Tuple
import json
import re
from datetime import datetime
import os
from dataclasses import dataclass

# Import your existing search system
try:
    from az_hierarchical_chunking import HybridSearchEngine, AzerbaijaniTextProcessor
except ImportError:
    print("Warning: az_hierarchical_chunking not found. Please ensure it's in the same directory.")


@dataclass
class DocumentMetadata:
    """Metadata for documents to track versions and contacts"""
    document_id: str
    title: str
    version: str
    last_updated: datetime
    contact_person: str
    contact_email: str
    contact_phone: str
    project_name: str
    document_type: str
    status: str


class GeminiConfig:
    """Enhanced configuration for Gemini AI model"""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')  # Using latest model

        # Enhanced generation configuration for government documents
        self.generation_config = genai.types.GenerationConfig(
            temperature=0.3,  # Lower temperature for more consistent formal writing
            top_p=0.9,
            top_k=40,
            max_output_tokens=4096,  # Increased for detailed opinions
        )

        # Strict safety settings for government use
        self.safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_MEDIUM_AND_ABOVE"
            }
        ]


class AzerbaijaniPromptTemplates:
    """Enhanced Azerbaijani language prompt templates"""

    SYSTEM_PROMPT = """Siz Azərbaycan Respublikasının Nazirliyi üçün sənəd təhlili və rəy hazırlayan AI assistantısınız. 

    Əsas vəzifələriniz:
    1. Dövlət sənədlərini dərin təhlil etmək
    2. Milli strategiya və qanunvericilik ilə uyğunluq yoxlamaq
    3. Peşəkar rəy və təkliflər vermək
    4. Azərbaycan dilində formal dövlət üslubunda yazmaq
    5. Əlaqəli sənədlər və kontakt məlumatları təqdim etmək

    Həmişə obyektiv, konstruktiv və faktlara əsaslanan rəylər verin.
    Rəsmi dövlət dilində, səlis və anlaşıqlı yazın.
    Hər rəydə əlaqəli qanunvericilik və strategiyalara istinad edin."""

    FORMAL_OPINION_TEMPLATE = """
    AZƏRBAYCAN RESPUBLİKASI
    {ministry_name}

    RƏY

    Sənədin adı: {document_title}
    Rəy tarixi: {analysis_date}
    Hazırlayan: AI Analitik Sistemi

    I. ÜMUMİ QİYMƏTLƏNDİRMƏ
    {general_assessment}

    II. ƏSAS MƏQAMLAR
    {key_points}

    III. MİLLİ STRATEGİYA İLƏ UYĞUNLUQ
    {strategy_alignment}

    IV. QANUNVERİCİLİK ASPEKTLƏRİ
    {legal_compliance}

    V. TÖVSİYƏLƏR
    {recommendations}

    VI. NƏTİCƏ
    {conclusion}

    VII. ƏLAQƏ MƏLUMATARI
    {contact_info}

    VIII. ƏLAQƏDAR SƏNƏDLƏR
    {related_documents}

    Rəy hazırlandı: {current_date}
    """

    RAG_CONTEXT_PROMPT = """
    Aşağıdakı məlumatları təhlil zamanı kontekst kimi istifadə edin:

    ƏLAQƏDAR SƏNƏDLƏR VƏ STRATEGİYALAR:
    {context_documents}

    QANUNVERİCİLİK BAZASI:
    {legal_framework}

    ƏLAQƏ MƏLUMATARI:
    {contact_information}
    """


class DocumentRegistry:
    """Registry for tracking document metadata and contacts"""

    def __init__(self):
        self.documents = {}
        self.contacts = {}
        self.projects = {}
        self.legal_framework = {}

    def register_document(self, metadata: DocumentMetadata):
        """Register a document with its metadata"""
        self.documents[metadata.document_id] = metadata

    def register_contact(self, person_id: str, name: str, position: str,
                         email: str, phone: str, projects: List[str]):
        """Register contact information"""
        self.contacts[person_id] = {
            'name': name,
            'position': position,
            'email': email,
            'phone': phone,
            'projects': projects
        }

    def get_project_contacts(self, project_name: str) -> List[Dict]:
        """Get all contacts for a specific project"""
        contacts = []
        for person_id, contact in self.contacts.items():
            if project_name in contact['projects']:
                contacts.append(contact)
        return contacts

    def get_latest_document_version(self, document_base_name: str) -> Optional[DocumentMetadata]:
        """Get the latest version of a document"""
        matching_docs = [
            doc for doc in self.documents.values()
            if document_base_name.lower() in doc.title.lower()
        ]

        if matching_docs:
            return max(matching_docs, key=lambda x: x.last_updated)
        return None


class EnhancedOpinionGenerator:
    """AI-powered opinion generator that uses existing azerbaijani_chunks.db"""

    def __init__(self, api_key: str, db_path: str = "azerbaijani_chunks.db"):
        self.gemini_config = GeminiConfig(api_key)
        self.templates = AzerbaijaniPromptTemplates()
        self.document_registry = DocumentRegistry()

        # ONLY load from existing database - NO chunking operations
        print(f"Loading existing chunks from: {db_path}")
        self.search_engine = HybridSearchEngine(
            chunks=None,  # No new chunks
            db_path=db_path,
            force_rebuild=False  # Never rebuild
        )

        # Verify chunks are loaded
        stats = self.search_engine.get_database_stats()
        print(f"Loaded {stats['total_chunks']} existing chunks from database")

        self._load_legal_framework()
        self._load_contacts()

    def _load_legal_framework(self):
        """Load legal framework and regulations"""
        self.legal_framework = {
            'digital_strategy': 'Rəqəmsal iqtisadiyyatın inkişafı üzrə strategiya',
            'national_priorities': 'Azərbaycan 2030: sosial-iqtisadi inkişafa dair Milli Prioritetlər',
            'constitution': 'Azərbaycan Respublikasının Konstitusiyası',
            'civil_service_law': 'Dövlət qulluğu haqqında qanun',
            'economy_law': 'İqtisadiyyat sahəsində qanunvericilik',
            'innovation_strategy': 'İnnovasiya və texnologiya inkişafı strategiyası'
        }

    def _load_contacts(self):
        """Load contact information"""
        # Sample contacts - replace with actual data from HR system
        self.document_registry.contacts = {
            'digital_strategy': {
                'name': 'Rəqəmsal İnkişaf Şöbəsi',
                'position': 'Şöbə müdiri',
                'email': 'digital@economy.gov.az',
                'phone': '+994 12 123 45 67',
                'projects': ['rəqəmsal_strategiya', 'e-government']
            },
            'innovation': {
                'name': 'İnnovasiya Mərkəzi',
                'position': 'Mərkəz rəhbəri',
                'email': 'innovation@economy.gov.az',
                'phone': '+994 12 123 45 68',
                'projects': ['innovasiya', 'texnologiya']
            }
        }

    def generate_comprehensive_opinion(self, document_text: str, document_title: str = "Sənəd",
                                       ministry_name: str = "İqtisadiyyat Nazirliyi") -> Dict[str, Any]:
        """Generate comprehensive opinion with detailed analysis and clear decision"""

        print(f"Generating comprehensive analysis for: {document_title}")
        print("Analyzing against existing strategy documents...")

        # Extract search terms from the NEW document
        search_terms = self._extract_key_terms(document_text, document_title)
        print(f"Search terms: {search_terms}")

        # Search through EXISTING chunks in database
        try:
            search_results = self.search_engine.search(
                query=search_terms,
                top_k=3,
                search_type='hybrid'
            )

            print(f"Found {len(search_results)} relevant existing strategy sections")
            context_info = self._prepare_strategic_context(search_results)

        except Exception as e:
            print(f"Database search failed: {e}")
            search_results = []
            context_info = "Mövcud strategiya bazasından kontekst əldə edilə bilmədi."

        # Enhanced detailed prompt for comprehensive analysis
        prompt = f"""{self.templates.SYSTEM_PROMPT}

    TAPŞIRIQ: Aşağıdakı yeni sənədə hərtərəfli və detallı təhlil aparın. Cavabınız formal dövlət üslubunda, ətraflı və struktur olmalıdır.

    YENİ SƏNƏD:
    Başlıq: {document_title}
    Məzmun: {document_text}

    MÖVCUD STRATEGİYA BAZASI:
    {context_info}

    TƏLƏB OLUNAN TƏHLİL STRUKTURU:

    **QƏTİ QƏRAR** (İlk öncə qərarı bildirin):
    [TƏSDİQ EDİLİR / RƏD EDİLİR / ŞƏRTLİ TƏSDİQ]

    **I. ÜMUMİ QİYMƏTLƏNDİRMƏ** (4-5 cümlə):
    - Sənədin əsas məqsədi və mahiyyəti
    - Strategiya ilə uyğunluq dərəcəsi (yüksək/orta/aşağı)
    - Ümumi qiymətləndirmə

    **II. MÜSBƏt TƏRƏFLƏR** (5-7 nöqtə, hər biri 2-3 cümlə):
    - Milli strategiya ilə uyğun olan konkret aspektlər
    - Rəqəmsal iqtisadiyyat hədəflərinə töhfə verən elementlər
    - İqtisadi artıma potensial müsbət təsiri
    - İnnovatıv və perspektivli təkliflər
    - Biznes inkişafına dəstək verən məqamlar

    **III. MƏNFİ TƏRƏFLƏR VƏ RİSKLƏR** (4-6 nöqtə, hər biri 2-3 cümlə):
    - Strategiya prioritetləri ilə ziddiyyət təşkil edən məqamlar
    - Maliyyə və resurs tələbləri
    - İcra çətinlikləri və maneələr
    - Potensial iqtisadi və sosial risklər
    - Qanunvericilik problemləri

    **IV. STRATEGİYA İLƏ UYĞUNLUQ TƏHLİLİ** (4-5 paraqraf):
    - "Azərbaycan 2030" prioritetləri ilə əlaqə
    - Rəqəmsal iqtisadiyyat hədəfləri ilə uyğunluq
    - Biznes aspekti üzrə qiymətləndirmə
    - Cəmiyyət aspekti üzrə qiymətləndirmə
    - Dövlət aspekti üzrə qiymətləndirmə

    **V. TÖVSİYƏLƏR** (5-8 konkret tövsiyə):
    - Təkmilləşdirmə təklifləri
    - Əlavə tədbirlər
    - İcra mexanizmləri
    - Risk azaldılması üsulları
    - Strategiya ilə daha yaxşı uyğunlaşdırma yolları

    **VI. QƏTİ QƏRAR VƏ ƏSASLANDIRMA** (3-4 paraqraf):
    - Qərarın ətraflı əsaslandırılması
    - Mövcud strategiya sənədlərinə istinadlar
    - Şərtli təsdiq halında konkret tələblər

    **VII. TƏTBİQ TƏLİMATI**:
    - Növbəti addımlar
    - Cavabdeh şəxslər
    - Müddətlər

    Hər bölməni detallı və əsaslandırılmış şəkildə yazın. Qısa cavablar verməyin.

    Əgər 90%-dən yuxarı uyğunluq aşkar etsən, tam şəkildə təsdiq et."""

        # Generate response
        try:
            response = self.gemini_config.model.generate_content(
                prompt,
                generation_config=self.gemini_config.generation_config,
                safety_settings=self.gemini_config.safety_settings
            )

            # Parse the detailed response
            opinion_data = self._parse_detailed_response(response.text)

            # Extract decision from response
            decision = self._extract_detailed_decision(response.text)

            return {
                'success': True,
                'opinion': opinion_data,
                'decision': decision,
                'document_title': document_title,
                'ministry_name': ministry_name,
                'existing_chunks_referenced': len(search_results),
                'database_chunks_total': self.search_engine.get_database_stats()['total_chunks'],
                'generated_at': datetime.now().isoformat(),
                'raw_response': response.text,
                'formatted_opinion': self._format_detailed_official_opinion(
                    opinion_data, decision, document_title, ministry_name, search_results, response.text
                )
            }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'document_title': document_title
            }

    def _format_detailed_official_opinion(self, opinion_data: Dict, decision: Dict,
                                          document_title: str, ministry_name: str,
                                          referenced_chunks: List, full_response: str) -> str:
        """Format detailed official opinion"""

        current_date = datetime.now().strftime("%d.%m.%Y")

        # Build referenced documents list
        referenced_docs = ""
        if referenced_chunks:
            doc_list = []
            for chunk, score, _ in referenced_chunks:
                doc_list.append(f"• {chunk.title} (Bölmə: {chunk.section_number}, Uyğunluq: {score:.3f})")
            referenced_docs = "\n".join(doc_list)

        # Use the full AI response if parsing failed
        main_content = full_response if not any(opinion_data.values()) else f"""
    I. ÜMUMİ QİYMƏTLƏNDİRMƏ
    {opinion_data.get('general_assessment', 'Qiymətləndirmə aparılmadı')}

    II. MÜSBƏt TƏRƏFLƏR
    {opinion_data.get('positive_aspects', 'Müsbət tərəflər müəyyən edilmədi')}

    III. MƏNFİ TƏRƏFLƏR VƏ RİSKLƏR
    {opinion_data.get('negative_aspects', 'Mənfi tərəflər müəyyən edilmədi')}

    IV. STRATEGİYA İLƏ UYĞUNLUQ TƏHLİLİ
    {opinion_data.get('strategy_alignment', 'Uyğunluq təhlili aparılmadı')}

    V. TÖVSİYƏLƏR
    {opinion_data.get('recommendations', 'Tövsiyələr verilmədi')}

    VI. QƏTİ QƏRAR VƏ ƏSASLANDIRMA
    {opinion_data.get('decision_reasoning', 'Qərar əsaslandırılmadı')}

    VII. TƏTBİQ TƏLİMATI
    {opinion_data.get('implementation_instructions', 'Təlimat verilmədi')}"""

        formatted_opinion = f"""
    AZƏRBAYCAN RESPUBLİKASI
    {ministry_name}

    RƏY VƏ QƏRAR

    QƏTİ QƏRAR: {decision.get('status', 'MÜƏYYƏN EDİLMƏDİ')}

    Sənədin adı: {document_title}
    Təhlil tarixi: {current_date}
    Həyata keçirən: AI Analitik Sistemi
    Əsas: "Rəqəmsal iqtisadiyyatın inkişafı üzrə Strategiya" (2025-2028)

    {main_content}

    VIII. İSTİFADƏ EDİLƏN STRATEGİYA SƏNƏDLƏRİ
    {referenced_docs}

    IX. TƏHLİL STATİSTİKASI
    • İstifadə edilən strategiya bölmələri: {len(referenced_chunks)}
    • Ümumi strategiya bazası: {self.search_engine.get_database_stats()['total_chunks']} bölmə
    • Təhlil metodu: Hibrid axtarış və AI analiz

    X. QƏRAR ÜZRƏ ƏK-TƏDBİRLƏR
    {decision.get('conditions', 'Əlavə şərtlər müəyyən edilmədi' if decision.get('status') == 'ŞƏRTLİ TƏSDİQ' else 'Əlavə tədbirlər tələb olunmur')}

    Hazırlanma tarixi: {current_date}
    Növbəti yenidən baxış: {current_date} tarixindən 6 ay sonra

    Bu qərar "Azərbaycan 2030: sosial-iqtisadi inkişafa dair Milli Prioritetlər" və 
    "Rəqəmsal iqtisadiyyatın inkişafı üzrə Strategiya"ya əsasən verilmişdir.
    """
        return formatted_opinion

    def _prepare_strategic_context(self, search_results: List[Tuple]) -> str:
        """Prepare strategic context from the 6 main strategy chunks"""

        if not search_results:
            return "Mövcud strategiya bazasında əlaqədar məlumat tapılmadı."

        context_parts = []
        context_parts.append("MÖVCUD 'RƏQƏMSAL İQTİSADİYYATIN İNKİŞAFI STRATEGİYASI' (2025-2028):")

        # Group results by strategy sections
        strategy_sections = {
            'xulasa': [],
            'beynelxalq_tecrube': [],
            'movcud_veziyyetin_tehlili': [],
            'hedef_gostericiiler': [],
            'prioritet_istiqametler': [],
            'maliyyelesdirme': []
        }

        for chunk, score, score_details in search_results:
            section_id = chunk.section_number

            # Categorize based on content/title
            if 'xülasə' in chunk.title.lower() or section_id == '1':
                strategy_sections['xulasa'].append((chunk, score))
            elif 'beynəlxalq' in chunk.title.lower() or section_id == '2':
                strategy_sections['beynelxalq_tecrube'].append((chunk, score))
            elif 'mövcud vəziyyət' in chunk.title.lower() or section_id == '3':
                strategy_sections['movcud_veziyyetin_tehlili'].append((chunk, score))
            elif 'hədəf' in chunk.title.lower() or 'məqsəd' in chunk.title.lower() or section_id == '4':
                strategy_sections['hedef_gostericiiler'].append((chunk, score))
            elif 'prioritet' in chunk.title.lower() or section_id == '5':
                strategy_sections['prioritet_istiqametler'].append((chunk, score))
            elif 'maliyyə' in chunk.title.lower() or section_id == '6':
                strategy_sections['maliyyelesdirme'].append((chunk, score))

        # Build context with most relevant sections
        for section_name, chunks in strategy_sections.items():
            if chunks:
                best_chunk, best_score = max(chunks, key=lambda x: x[1])

                section_titles = {
                    'xulasa': 'STRATEGİYANIN XÜLASƏSİ',
                    'beynelxalq_tecrube': 'BEYNƏLXALQ TƏCRÜBƏ VƏ TRENDLƏR',
                    'movcud_veziyyetin_tehlili': 'MÖVCUD VƏZİYYƏTİN TƏHLİLİ',
                    'hedef_gostericiiler': 'HƏDƏF GÖSTƏRİCİLƏRİ VƏ MƏQSƏDLƏR',
                    'prioritet_istiqametler': 'PRİORİTET İSTİQAMƏTLƏR',
                    'maliyyelesdirme': 'MALİYYƏLƏŞDİRMƏ MEXANİZMLƏRİ'
                }

                context_parts.append(f"""
    {section_titles.get(section_name, section_name.upper())}:
    Əlaqəlilik: {best_score:.3f}
    {best_chunk.content[:600]}...
    """)

        return "\n".join(context_parts)

    def _parse_detailed_response(self, response_text: str) -> Dict[str, str]:
        """Parse detailed AI response with proper section extraction"""

        sections = {
            'general_assessment': '',
            'positive_aspects': '',
            'negative_aspects': '',
            'strategy_alignment': '',
            'recommendations': '',
            'decision_reasoning': '',
            'implementation_instructions': '',
            'full_response': response_text
        }

        # More robust parsing patterns for Azerbaijani text
        section_patterns = {
            'general_assessment': r'(?:I\.|1\.)\s*(?:ÜMUMİ|Ümumi).*?QİYMƏTLƏNDİRMƏ.*?:?\s*\*?\*?\s*(.+?)(?=\*\*II\.|II\.|2\.|$)',
            'positive_aspects': r'(?:II\.|2\.)\s*(?:MÜSBƏt|Müsbət).*?TƏRƏFLƏR.*?:?\s*\*?\*?\s*(.+?)(?=\*\*III\.|III\.|3\.|$)',
            'negative_aspects': r'(?:III\.|3\.)\s*(?:MƏNFİ|Mənfi).*?TƏRƏFLƏR.*?:?\s*\*?\*?\s*(.+?)(?=\*\*IV\.|IV\.|4\.|$)',
            'strategy_alignment': r'(?:IV\.|4\.)\s*(?:STRATEGİYA|Strategiya).*?UYĞUNLUQ.*?:?\s*\*?\*?\s*(.+?)(?=\*\*V\.|V\.|5\.|$)',
            'recommendations': r'(?:V\.|5\.)\s*(?:TÖVSİYƏLƏR|Tövsiyələr).*?:?\s*\*?\*?\s*(.+?)(?=\*\*VI\.|VI\.|6\.|$)',
            'decision_reasoning': r'(?:VI\.|6\.)\s*(?:QƏTİ|Qəti).*?QƏRAR.*?:?\s*\*?\*?\s*(.+?)(?=\*\*VII\.|VII\.|7\.|$)',
            'implementation_instructions': r'(?:VII\.|7\.)\s*(?:TƏTBİQ|Tətbiq).*?:?\s*\*?\*?\s*(.+?)(?=\*\*VIII\.|VIII\.|8\.|$)'
        }

        for key, pattern in section_patterns.items():
            match = re.search(pattern, response_text, re.IGNORECASE | re.DOTALL)
            if match:
                sections[key] = match.group(1).strip()

        return sections

    def _extract_detailed_decision(self, response_text: str) -> Dict[str, str]:
        """Extract detailed decision information"""

        decision_data = {
            'status': 'MÜƏYYƏN EDİLMƏDİ',
            'reasoning': '',
            'conditions': '',
            'next_steps': ''
        }

        text_lower = response_text.lower()

        # Look for decision at the beginning of response
        decision_start_pattern = r'(?:\*\*QƏTİ QƏRAR\*\*.*?[:]\s*)?(\[?(?:TƏSDİQ EDİLİR|RƏD EDİLİR|ŞƏRTLİ TƏSDİQ)\]?)'
        decision_match = re.search(decision_start_pattern, response_text, re.IGNORECASE)

        if decision_match:
            status_text = decision_match.group(1).strip('[]').upper()
            if 'TƏSDİQ EDİLİR' in status_text:
                decision_data['status'] = 'TƏSDİQ EDİLİR'
            elif 'RƏD EDİLİR' in status_text:
                decision_data['status'] = 'RƏD EDİLİR'
            elif 'ŞƏRTLİ' in status_text:
                decision_data['status'] = 'ŞƏRTLİ TƏSDİQ'

        # Extract reasoning from section VI
        reasoning_pattern = r'(?:VI\.|6\.)\s*(?:QƏTİ|Qəti).*?QƏRAR.*?ƏSASLANDIRMA.*?:?\s*\*?\*?\s*(.+?)(?=\*\*VII\.|VII\.|7\.|$)'
        reasoning_match = re.search(reasoning_pattern, response_text, re.IGNORECASE | re.DOTALL)
        if reasoning_match:
            decision_data['reasoning'] = reasoning_match.group(1).strip()

        # Extract conditions if conditional approval
        if 'ŞƏRTLİ' in decision_data['status']:
            conditions_pattern = r'(?:şərt|şərtlər|tələblər).*?:?\s*(.+?)(?=\n\n|\*\*|$)'
            conditions_match = re.search(conditions_pattern, response_text, re.IGNORECASE | re.DOTALL)
            if conditions_match:
                decision_data['conditions'] = conditions_match.group(1).strip()

        return decision_data

    def _format_official_decision_opinion(self, opinion_data: Dict, decision: Dict,
                                          document_title: str, ministry_name: str,
                                          referenced_chunks: List) -> str:
        """Format official opinion with decision"""

        current_date = datetime.now().strftime("%d.%m.%Y")

        # Build referenced documents list
        referenced_docs = ""
        if referenced_chunks:
            doc_list = []
            for chunk, score, _ in referenced_chunks[:3]:
                doc_list.append(f"• {chunk.title} (Bölmə: {chunk.section_number}, Uyğunluq: {score:.3f})")
            referenced_docs = "\n".join(doc_list)

        formatted_opinion = f"""
    AZƏRBAYCAN RESPUBLİKASI
    {ministry_name}

    RƏY VƏ QƏRAR

    Sənədin adı: {document_title}
    Təhlil tarixi: {current_date}
    Həyata keçirən: AI Analitik Sistemi
    Əsas: "Rəqəmsal iqtisadiyyatın inkişafı üzrə Strategiya" (2025-2028)

    I. ÜMUMİ QİYMƏTLƏNDİRMƏ
    {opinion_data.get('general_assessment', 'Qiymətləndirmə aparılmadı')}

    II. MÜSBƏt TƏRƏFLƏR
    {opinion_data.get('positive_aspects', 'Müsbət tərəflər müəyyən edilmədi')}

    III. MƏNFİ TƏRƏFLƏR VƏ RİSKLƏR
    {opinion_data.get('negative_aspects', 'Mənfi tərəflər müəyyən edilmədi')}

    IV. STRATEGİYA İLƏ UYĞUNLUQ TƏHLİLİ
    {opinion_data.get('strategy_alignment', 'Uyğunluq təhlili aparılmadı')}

    V. TÖVSİYƏLƏR
    {opinion_data.get('recommendations', 'Tövsiyələr verilmədi')}

    VI. QƏTİ QƏRAR

    QƏRAR: {decision.get('status', 'MÜƏYYƏN EDİLMƏDİ')}

    ƏSASLANDIRMA:
    {decision.get('reasoning', 'Əsaslandırma verilmədi')}

    {f"ŞƏRTLƏR: {decision.get('conditions', '')}" if decision.get('conditions') else ""}

    VII. İSTİFADƏ EDİLƏN STRATEGİYA SƏNƏDLƏRİ
    {referenced_docs}

    VIII. TƏHLİL STATİSTİKASI
    • İstifadə edilən strategiya bölmələri: {len(referenced_chunks)}
    • Ümumi strategiya bazası: {self.search_engine.get_database_stats()['total_chunks']} bölmə
    • Təhlil metodu: Hibrid axtarış və AI analiz

    IX. TƏTBİQ TƏLİMATI
    Bu qərar "Azərbaycan 2030: sosial-iqtisadi inkişafa dair Milli Prioritetlər" və 
    "Rəqəmsal iqtisadiyyatın inkişafı üzrə Strategiya"ya əsasən verilmişdir.

    Hazırlanma tarixi: {current_date}
    Növbəti yenidən baxış: {current_date} tarixindən 1 il sonra
    """
        return formatted_opinion

    def _extract_key_terms(self, document_text: str, document_title: str) -> str:
        """Extract key terms for searching existing database"""

        # Use title + key parts of content
        important_words = []

        # Add title words (filter out short words)
        title_words = [word for word in document_title.split() if len(word) > 3]
        important_words.extend(title_words)

        # Add key Azerbaijani terms from content
        azerbaijani_keywords = [
            'strategiya', 'rəqəmsal', 'iqtisadiyyat', 'inkişaf', 'plan',
            'məqsəd', 'hədəf', 'texnologiya', 'innovasiya', 'transformasiya',
            'dövlət', 'nazirlik', 'qanun', 'tətbiq', 'həyata', 'keçirilməsi',
            'biznes', 'ticarət', 'elektron', 'platforma', 'rəqəmsallaşma',
            'maliyyə', 'investisiya', 'dəstək', 'mexanizm', 'proqram'
        ]

        # Check which keywords appear in the document
        document_lower = document_text.lower()
        for keyword in azerbaijani_keywords:
            if keyword in document_lower:
                important_words.append(keyword)

        # Remove duplicates and join
        unique_terms = list(set(important_words))
        return ' '.join(unique_terms[:8])  # Max 8 terms for focused search
