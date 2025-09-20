import json
import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# Import your existing components
from az_hierarchical_chunking import HybridSearchEngine, AzerbaijaniTextProcessor

# Set API key directly
GEMINI_API_KEY = "AIzaSyCcoEj8Hyy017kZkhZZ4GYNB30iU3DfBoI"


class ChunkObject:
    """Simple chunk object that matches the expected interface"""

    def __init__(self, chunk_id: str, title: str, content: str, level: int = 1,
                 section_number: str = "", chunk_type: str = "content", tables: List = None):
        self.chunk_id = chunk_id
        self.title = title
        self.content = content
        self.level = level
        self.section_number = section_number or chunk_id
        self.chunk_type = chunk_type
        self.tables = tables or []

    def __repr__(self):
        return f"ChunkObject(id={self.chunk_id}, title='{self.title[:30]}...')"


class ProjectAnalysisRAG:
    """
    RAG System for Project Document Analysis
    Combines BM25, TF-IDF, and Gemini AI to analyze documents against regulatory chunks
    Specially designed for Azerbaijani language documents
    """

    def __init__(self, chunk_file_path: str = "chunk.json", enable_ai: bool = True):
        """Initialize the RAG system"""
        self.logger = self._setup_logging()
        self.enable_ai = enable_ai

        # Load chunks data with proper encoding for Azerbaijani
        self.chunks_data = self._load_chunks(chunk_file_path)

        # Convert chunks to proper format for HybridSearchEngine
        self.chunks_list = self._prepare_chunks_for_search(self.chunks_data)

        # Initialize components
        self.text_processor = AzerbaijaniTextProcessor()
        self.search_engine = HybridSearchEngine(
            chunks=self.chunks_list,
            text_processor=self.text_processor
        )

        # Initialize Gemini AI if enabled
        self.opinion_generator = None
        if enable_ai and GEMINI_API_KEY:
            try:
                from gemini_integration import OpinionGenerator
                self.opinion_generator = OpinionGenerator(
                    api_key=GEMINI_API_KEY,
                    search_engine=self.search_engine
                )
                self.logger.info("AI analysis enabled")
            except Exception as e:
                self.logger.warning(f"AI analysis disabled due to error: {str(e)}")
                self.enable_ai = False

        self.logger.info(f"RAG System initialized with {len(self.chunks_data)} chunks")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
            ]
        )
        return logging.getLogger(__name__)

    def _load_chunks(self, file_path: str) -> Dict:
        """Load chunks from JSON file with proper Azerbaijani language support"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            self.logger.info(f"Loaded {len(chunks)} chunks from {file_path}")
            return chunks
        except Exception as e:
            self.logger.error(f"Error loading chunks: {str(e)}")
            raise

    def _prepare_chunks_for_search(self, chunks_data: Dict) -> List[ChunkObject]:
        """Convert JSON chunks to ChunkObject instances for HybridSearchEngine"""
        chunks_list = []

        for chunk_id, chunk_data in chunks_data.items():
            # Create a ChunkObject compatible with the search engine
            chunk_obj = ChunkObject(
                chunk_id=chunk_id,
                title=chunk_data.get('title', ''),
                content=chunk_data.get('content', ''),
                level=1,  # Default level
                section_number=chunk_id,
                chunk_type='content'  # Default type
            )
            chunks_list.append(chunk_obj)

        return chunks_list

    def analyze_project_document(self,
                                 document_text: str,
                                 document_title: str = "Layihə Sənədi",
                                 top_k: int = 3,
                                 min_similarity: float = 0.1) -> Dict[str, Any]:
        """
        Main method to analyze project document against regulatory framework
        """

        self.logger.info(f"Analyzing document: {document_title}")

        # Step 1: Search relevant regulatory chunks
        search_results = self._search_relevant_chunks(
            document_text, top_k, min_similarity
        )

        # Step 2: Categorize findings into acceptable/unacceptable reasons
        categorized_analysis = self._categorize_compliance(
            document_text, search_results
        )

        # Step 3: Generate AI-powered detailed analysis (if enabled)
        ai_analysis = self._generate_ai_analysis(
            document_text, document_title, search_results
        ) if self.enable_ai else self._generate_mock_ai_analysis()

        # Step 4: Compile comprehensive results
        final_analysis = self._compile_analysis_results(
            document_text, document_title, search_results,
            categorized_analysis, ai_analysis
        )

        self.logger.info("Analysis completed successfully")
        return final_analysis

    def _search_relevant_chunks(self,
                                document_text: str,
                                top_k: int,
                                min_similarity: float) -> List[Dict]:
        """Search for relevant chunks using hybrid search"""

        self.logger.info(f"Searching for {top_k} most relevant chunks")

        # Use hybrid search (BM25 + TF-IDF + custom features)
        search_tuples = self.search_engine.search(
            query=document_text,
            top_k=top_k
        )

        # Convert tuples to dictionary format and filter by similarity
        search_results = []
        for chunk, combined_score, score_details in search_tuples:
            if combined_score >= min_similarity:
                result = {
                    'main_chunk': {
                        'chunk_id': getattr(chunk, 'chunk_id', 'unknown'),
                        'title': chunk.title,
                        'content': chunk.content,
                        'level': chunk.level,
                        'section_number': chunk.section_number,
                        'chunk_type': chunk.chunk_type
                    },
                    'similarity_score': combined_score,
                    'score_details': score_details
                }
                search_results.append(result)

        self.logger.info(f"Found {len(search_results)} chunks above similarity threshold")
        return search_results

    def _categorize_compliance(self,
                               document_text: str,
                               search_results: List[Dict]) -> Dict[str, List[Dict]]:
        """Categorize compliance into acceptable and unacceptable reasons"""

        acceptable_reasons = []
        unacceptable_reasons = []
        neutral_aspects = []

        # Enhanced Azerbaijani keywords for categorization
        positive_keywords = [
            'uyğun', 'müvafiq', 'razılaşır', 'dəstəkləyir', 'təsdiqləyir',
            'qəbul edilir', 'tövsiyə edilir', 'məqbul', 'yararlı', 'müsbet',
            'təmin edir', 'həyata keçirir', 'nail olur', 'məqsədi güdür',
            'inkişaf', 'tərəqqi', 'innovasiya', 'modernləşdirmə', 'transformasiya',
            'rəqəmsal', 'texnologiya', 'dördüncü sənaye inqilabı', 'strategiya'
        ]

        negative_keywords = [
            'uyğun deyil', 'ziddiyyət', 'pozğunluq', 'qadağan', 'qəbul edilmir',
            'çatışmazlıq', 'problem', 'risk', 'təhlükə', 'mümkün deyil',
            'icazə verilmir', 'məhdudlaşdırır', 'pozuntuq', 'qadağandır',
            'yolverilməz', 'problemli', 'tam hazırlanmamış', 'kifayət qədər yox'
        ]

        requirement_keywords = [
            'tələb olunur', 'lazımdır', 'zəruridir', 'məcburidir', 'vacibdir',
            'şərt kimi', 'əsasdır', 'əsas götürülür', 'nəzərdə tutulur',
            'həyata keçirilməlidir', 'təmin edilməlidir', 'yaradılmalıdır'
        ]

        for result in search_results:
            chunk_content = result.get('main_chunk', {}).get('content', '')
            chunk_title = result.get('main_chunk', {}).get('title', '')
            similarity = result.get('similarity_score', 0)

            # Analyze chunk content for compliance indicators
            compliance_analysis = self._analyze_chunk_compliance(
                document_text, chunk_content, chunk_title, similarity,
                positive_keywords, negative_keywords, requirement_keywords
            )

            # Categorize based on analysis
            if compliance_analysis['compliance_type'] == 'acceptable':
                acceptable_reasons.append(compliance_analysis)
            elif compliance_analysis['compliance_type'] == 'unacceptable':
                unacceptable_reasons.append(compliance_analysis)
            else:
                neutral_aspects.append(compliance_analysis)

        return {
            'acceptable_reasons': acceptable_reasons,
            'unacceptable_reasons': unacceptable_reasons,
            'neutral_aspects': neutral_aspects
        }

    def _analyze_chunk_compliance(self,
                                  document_text: str,
                                  chunk_content: str,
                                  chunk_title: str,
                                  similarity: float,
                                  positive_keywords: List[str],
                                  negative_keywords: List[str],
                                  requirement_keywords: List[str]) -> Dict[str, Any]:
        """Analyze individual chunk for compliance using Azerbaijani language patterns"""

        doc_lower = document_text.lower()
        chunk_lower = chunk_content.lower()

        # Count keyword matches
        positive_matches = sum(1 for keyword in positive_keywords if keyword in chunk_lower)
        negative_matches = sum(1 for keyword in negative_keywords if keyword in chunk_lower)
        requirement_matches = sum(1 for keyword in requirement_keywords if keyword in chunk_lower)

        # Check for common topic overlap
        doc_words = set(doc_lower.split())
        chunk_words = set(chunk_lower.split())
        word_overlap = len(doc_words.intersection(chunk_words))

        # Enhanced compliance detection
        compliance_type = 'neutral'
        confidence = 0.0

        # Check for specific negative patterns
        negative_patterns = [
            'hazırlanmamış', 'yox', 'kifayət qədər', 'problemli aspektlər',
            'çatışmazlıq', 'tələb olunur'
        ]

        strong_negative = sum(1 for pattern in negative_patterns if pattern in chunk_lower)

        # High similarity threshold - more weight to content analysis
        if similarity > 0.5:
            if strong_negative > 0 or negative_matches > positive_matches:
                compliance_type = 'unacceptable'
                confidence = min(0.9, 0.5 + (negative_matches * 0.1))
            elif positive_matches > 0 or requirement_matches > 0:
                compliance_type = 'acceptable'
                confidence = min(0.9, 0.6 + (positive_matches * 0.1))
            else:
                compliance_type = 'neutral'
                confidence = similarity

        # Medium similarity threshold
        elif similarity > 0.2:
            if strong_negative > 0 or negative_matches > 1:
                compliance_type = 'unacceptable'
                confidence = min(0.8, 0.4 + (negative_matches * 0.1))
            elif positive_matches > negative_matches:
                compliance_type = 'acceptable'
                confidence = min(0.8, 0.4 + (positive_matches * 0.1))
            else:
                compliance_type = 'requires_attention'
                confidence = similarity

        return {
            'chunk_title': chunk_title,
            'chunk_content': chunk_content[:400] + '...' if len(chunk_content) > 400 else chunk_content,
            'similarity_score': similarity,
            'compliance_type': compliance_type,
            'confidence_score': confidence,
            'positive_matches': positive_matches,
            'negative_matches': negative_matches,
            'requirement_matches': requirement_matches,
            'word_overlap': word_overlap,
            'analysis_reason': self._get_compliance_reason_az(
                compliance_type, similarity, positive_matches, negative_matches, requirement_matches
            )
        }

    def _get_compliance_reason_az(self,
                                  compliance_type: str,
                                  similarity: float,
                                  positive_matches: int,
                                  negative_matches: int,
                                  requirement_matches: int) -> str:
        """Generate human-readable compliance reason in Azerbaijani"""

        if compliance_type == 'acceptable':
            if positive_matches > 0:
                return f"Sənəd məzmunu müvafiq qanunvericilik çərçivəsinə uyğundur. {positive_matches} müsbət göstərici aşkar edilib (oxşarlıq: {similarity:.3f})"
            else:
                return f"Sənəd ümumi olaraq tələblərə cavab verir (oxşarlıq: {similarity:.3f})"

        elif compliance_type == 'unacceptable':
            return f"Qanunvericilik tələbləri ilə ziddiyyət aşkar edilib. {negative_matches} mənfi göstərici mövcuddur (oxşarlıq: {similarity:.3f})"

        elif compliance_type == 'requires_attention':
            if requirement_matches > 0:
                return f"Əlavə tələblər və şərtlər nəzərə alınmalıdır. {requirement_matches} məcburi tələb aşkar edilib (oxşarlıq: {similarity:.3f})"
            else:
                return f"Diqqət tələb edən aspektlər mövcuddur (oxşarlıq: {similarity:.3f})"

        else:
            return f"Neytral məzmun - əlavə təhlil tələb olunur (oxşarlıq: {similarity:.3f})"

    def _generate_ai_analysis(self,
                              document_text: str,
                              document_title: str,
                              search_results: List[Dict]) -> Dict[str, Any]:
        """Generate comprehensive AI analysis using Gemini"""

        if not self.opinion_generator:
            return self._generate_mock_ai_analysis()

        self.logger.info("Generating AI-powered analysis")

        # Prepare context chunks for AI analysis
        context_chunks = [
            {
                'main_chunk': result.get('main_chunk', {}),
                'similarity_score': result.get('similarity_score', 0)
            }
            for result in search_results[:3]  # Top 3 most relevant
        ]

        try:
            # Generate opinion
            opinion_result = self.opinion_generator.generate_opinion(
                document_text=document_text,
                document_title=document_title,
                context_chunks=context_chunks
            )

            # Generate suggestions
            suggestion_result = self.opinion_generator.generate_suggestion(
                document_text=document_text,
                document_title=document_title,
                context_chunks=context_chunks,
                suggestion_type="improvement"
            )

            return {
                'ai_opinion': opinion_result,
                'ai_suggestions': suggestion_result
            }
        except Exception as e:
            self.logger.warning(f"AI analysis failed: {str(e)}")
            return self._generate_mock_ai_analysis()

    def _generate_mock_ai_analysis(self) -> Dict[str, Any]:
        """Generate mock AI analysis when AI is not available"""
        return {
            'ai_opinion': {
                'success': False,
                'error': 'AI təhlili mövcud deyil - API açarı problemi və ya xəta'
            },
            'ai_suggestions': {
                'success': False,
                'error': 'AI təklifləri mövcud deyil - API açarı problemi və ya xəta'
            }
        }

    def _compile_analysis_results(self,
                                  document_text: str,
                                  document_title: str,
                                  search_results: List[Dict],
                                  categorized_analysis: Dict[str, List[Dict]],
                                  ai_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Compile all analysis results into final report"""

        # Calculate overall compliance score
        total_chunks = len(search_results)
        acceptable_count = len(categorized_analysis['acceptable_reasons'])
        unacceptable_count = len(categorized_analysis['unacceptable_reasons'])

        if total_chunks > 0:
            compliance_score = acceptable_count / total_chunks
            risk_score = unacceptable_count / total_chunks
        else:
            compliance_score = 0
            risk_score = 0

        # Enhanced recommendation logic
        if risk_score > 0.3:
            overall_recommendation = "QƏBUL EDİLMİR"
            recommendation_reason = "Ciddi qanunvericilik pozuntuları aşkar edilib"
        elif compliance_score >= 0.6 and risk_score <= 0.2:
            overall_recommendation = "QƏBUL EDİLİR"
            recommendation_reason = "Layihə əsasən müvafiq qanunvericilik tələblərinə uyğundur"
        elif compliance_score >= 0.3:
            overall_recommendation = "ŞƏRTLI QƏBUL"
            recommendation_reason = "Bəzi düzəlişlər və əlavə tədbirlər tələb olunur"
        else:
            overall_recommendation = "ƏLAVƏ ARAŞDIRMA TƏLƏBİ"
            recommendation_reason = "Əsaslı yenidənbaxım və əlavə sənədləşdirmə lazımdır"

        return {
            'document_info': {
                'title': document_title,
                'text_length': len(document_text),
                'analysis_date': datetime.now().strftime("%d.%m.%Y %H:%M"),
                'language': 'Azerbaijani'
            },
            'search_statistics': {
                'total_chunks_in_database': len(self.chunks_data),
                'relevant_chunks_found': len(search_results),
                'average_similarity': sum(r.get('similarity_score', 0) for r in search_results) / len(
                    search_results) if search_results else 0,
                'search_method': 'Hybrid (BM25 + TF-IDF + Custom Features)'
            },
            'compliance_analysis': {
                'overall_score': round(compliance_score, 3),
                'risk_score': round(risk_score, 3),
                'overall_recommendation': overall_recommendation,
                'recommendation_reason': recommendation_reason,
                'acceptable_reasons': categorized_analysis['acceptable_reasons'],
                'unacceptable_reasons': categorized_analysis['unacceptable_reasons'],
                'neutral_aspects': categorized_analysis['neutral_aspects']
            },
            'detailed_findings': {
                'top_relevant_chunks': search_results[:3],
                'compliance_statistics': {
                    'acceptable_count': acceptable_count,
                    'unacceptable_count': unacceptable_count,
                    'neutral_count': len(categorized_analysis['neutral_aspects']),
                    'total_analyzed': total_chunks
                }
            },
            'ai_analysis': ai_analysis,
            'recommendations': {
                'immediate_actions': self._generate_immediate_actions(categorized_analysis, risk_score),
                'next_steps': self._generate_next_steps(compliance_score, risk_score, categorized_analysis)
            }
        }

    def _generate_immediate_actions(self, categorized_analysis: Dict, risk_score: float) -> List[str]:
        """Generate immediate action items in Azerbaijani"""
        actions = []

        if risk_score > 0.3:
            actions.append("TƏCİLİ: Aşkar edilən qanunvericilik pozuntuları dərhal aradan qaldırılmalıdır")

        if categorized_analysis['unacceptable_reasons']:
            actions.append(
                f"{len(categorized_analysis['unacceptable_reasons'])} problemli məqam üçün düzəliş tələb olunur")

        if len(categorized_analysis['neutral_aspects']) > 3:
            actions.append("Qeyri-müəyyən aspektlər üçün əlavə hüquqi məsləhət alınmalıdır")

        if not actions:
            actions.append("Hal-hazırda təcili tədbir tələb olunmur")

        return actions

    def _generate_next_steps(self, compliance_score: float, risk_score: float, categorized_analysis: Dict) -> List[str]:
        """Generate next steps based on analysis in Azerbaijani"""
        steps = []

        if risk_score > 0.3:
            steps.extend([
                "Sənədin əsaslı yenidən işlənməsi",
                "Hüquqi ekspert rəyinin alınması",
                "Aidiyyəti nazirlik və qurumlarla razılaşdırma",
                "Problemli bəndlərin tamamilə yenidən yazılması"
            ])
        elif compliance_score < 0.4:
            steps.extend([
                "Müəyyən edilmiş çatışmazlıqların aradan qaldırılması",
                "Əlavə sənədləşdirmə və əsaslandırma",
                "İkinci mərhələ ekspert qiymətləndirməsi"
            ])
        elif compliance_score < 0.7:
            steps.extend([
                "Kiçik düzəlişlərin həyata keçirilməsi",
                "Son nəzarət və yoxlama",
                "Mərhələli tətbiq planının hazırlanması"
            ])
        else:
            steps.extend([
                "Son redaktə və formatlaşdırma",
                "Rəsmi təsdiq üçün təqdim",
                "İcra mexanizminin işlənib hazırlanması"
            ])

        return steps


def test_with_different_documents():
    """Test function with different types of documents"""

    # Test documents
    test_documents = [
        {
            "title": "Qeyri-qanuni Mədən Çıxarılması və Ekoloji Pozğunluq Layihəsi",
            "text": """Bu layihə çərçivəsində ölkənin qorunan təbiət ərazilərində qanunsuz mədən çıxarılması fəaliyyəti nəzərdə tutulur. Layihə heç bir ekoloji təsir qiymətləndirməsi aparılmadan və müvafiq icazələr alınmadan həyata keçiriləcək.

Əsas Məqsədlər:
- Milli parklar ərazisində qadağan edilmiş mədən işləri
- Çay və çayların çirkləndirilməsi
- Meşə sahələrinin qanunsuz məhv edilməsi
- Nadir heyvan növlərinin yaşayış mühitinin dağıdılması

Maliyyə Sxemi:
Layihənin maliyyələşdirilməsi tamamilə qeyri-şəffaf mənbələrdən aparılacaq. Heç bir hesabat və ya nəzarət mexanizmi nəzərdə tutulmur. Gəlirlər offshore hesablarda saxlanılacaq və vergi ödənilməyəcək.

Texniki Detallar:
- Köhnə və təhlükəli avadanlıqların istifadəsi
- İşçi təhlükəsizliyi qaydalarının pozulması
- Zəhərli tullantıların çaylara axıdılması
- Atmosferə zərərli qazların buraxılması

Sosial Təsir:
Yerli əhalinin razılığı alınmayacaq. Ərazidəki kəndlər məcburi köçürüləcək. Tarixi və mədəni abidələr dağıdılacaq. Ənənəvi yaşayış tərzi pozulacaq.

Hüquqi Status:
Bu layihə qanunvericilik tələblərinə zidd olaraq hazırlanmışdır. Heç bir icazə sənədi əldə edilməyəcək. Beynəlxalq ekoloji konvensiyalar məhəl qoyulmayacaq.

Rəqəmsal Texnologiyalar:
Layihədə müasir rəqəmsal həllər istifadə edilməyəcək. Monitorinq sistemləri quraşdırılmayacaq. Məlumatların şəffaflığı təmin edilməyəcək.

Qanunsuz Fəaliyyətlər:
- Korrupsiya sxemləri
- Rüşvətxorluq
- Sənəd saxtakarlığı
- İctimai malın mənimsənilməsi
- Çirklənmənin gizlədilməsi
"""
        },
        {
            "title": "Atlarin cinsi istismari",
            "text": """Esshek at her bir shey zoofil dayi pkk zohrab"""
        }
    ]

    try:
        # Initialize RAG system with AI enabled
        print("Sistem yüklənir...")
        rag_system = ProjectAnalysisRAG("chunk.json", enable_ai=True)

        for i, doc in enumerate(test_documents, 1):
            print(f"\n{'=' * 80}")
            print(f"TEST {i}: {doc['title']}")
            print('=' * 80)

            result = rag_system.analyze_project_document(
                document_text=doc['text'],
                document_title=doc['title'],
                top_k=3,
                min_similarity=0.1
            )

            # Print summary
            compliance = result['compliance_analysis']
            print(f"🏆 Qiymət: {compliance['overall_recommendation']}")
            print(f"📊 Uyğunluq: {compliance['overall_score']:.2f} | Risk: {compliance['risk_score']:.2f}")
            print(f"💡 Səbəb: {compliance['recommendation_reason']}")
            print(f"✅ Qəbul edilən: {len(compliance['acceptable_reasons'])}")
            print(f"❌ Problem: {len(compliance['unacceptable_reasons'])}")
            print(f"⚪ Neytral: {len(compliance['neutral_aspects'])}")

            # Print some details
            if compliance['acceptable_reasons']:
                print(f"\n🟢 QƏBUL EDİLƏN SƏBƏBLƏR:")
                for reason in compliance['acceptable_reasons'][:2]:
                    print(f"   • {reason['analysis_reason']}")

            if compliance['unacceptable_reasons']:
                print(f"\n🔴 PROBLEMLI SƏBƏBLƏR:")
                for reason in compliance['unacceptable_reasons'][:2]:
                    print(f"   • {reason['analysis_reason']}")

            # AI analysis status
            ai_opinion = result['ai_analysis']['ai_opinion']
            if ai_opinion.get('success', False):
                print(f"\n🤖 AI TƏHLİLİ: Uğurla tamamlandı")
            else:
                print(f"🤖 AI TƏHLİLİ: {ai_opinion.get('error', 'Xəta baş verdi')}")

        return True

    except Exception as e:
        print(f"Xəta baş verdi: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Run the comprehensive test
    test_with_different_documents()