# hybrid_search.py
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from rank_bm25 import BM25Okapi
from collections import defaultdict
import re
import hashlib
import json
import time
import sqlite3
from datetime import datetime
import pickle
import os


class DatabaseManager:
    """SQLite database manager for storing chunks and search indices"""

    def __init__(self, db_path: str = "azerbaijani_chunks.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create chunks table
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS chunks
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           chunk_id
                           TEXT
                           UNIQUE,
                           title
                           TEXT,
                           content
                           TEXT,
                           level
                           INTEGER,
                           section_number
                           TEXT,
                           chunk_type
                           TEXT,
                           has_tables
                           BOOLEAN,
                           content_length
                           INTEGER,
                           preprocessed_text
                           TEXT,
                           tokens
                           TEXT, -- JSON array of tokens
                           domain_features
                           TEXT, -- JSON object
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           updated_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       ''')

        # Create search indices table for storing BM25 and TF-IDF data
        cursor.execute('''
                       CREATE TABLE IF NOT EXISTS search_indices
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY,
                           index_name
                           TEXT
                           UNIQUE,
                           index_data
                           BLOB, -- Pickled search index
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           updated_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       ''')

        # Create full-text search index on content
        cursor.execute('''
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            chunk_id,
            title,
            content,
            preprocessed_text
        )
        ''')

        conn.commit()
        conn.close()
        print(f"Database initialized: {self.db_path}")

    def save_chunk(self, chunk, chunk_index: int, preprocessed_text: str,
                   tokens: List[str], domain_features: Dict[str, float]) -> str:
        """Save a chunk to the database"""
        chunk_id = f"chunk_{chunk_index}_{self._generate_chunk_hash(chunk)}"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute('''
            INSERT OR REPLACE INTO chunks 
            (chunk_id, title, content, level, section_number, chunk_type, 
             has_tables, content_length, preprocessed_text, tokens, domain_features, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                chunk_id,
                chunk.title,
                chunk.content,
                chunk.level,
                chunk.section_number,
                chunk.chunk_type,
                bool(len(chunk.tables) > 0),
                len(chunk.content),
                preprocessed_text,
                json.dumps(tokens, ensure_ascii=False),
                json.dumps(domain_features, ensure_ascii=False),
                datetime.now().isoformat()
            ))

            # Also add to FTS index
            cursor.execute('''
            INSERT OR REPLACE INTO chunks_fts 
            (chunk_id, title, content, preprocessed_text)
            VALUES (?, ?, ?, ?)
            ''', (chunk_id, chunk.title, chunk.content, preprocessed_text))

            conn.commit()
            return chunk_id

        except Exception as e:
            print(f"Error saving chunk {chunk_id}: {str(e)}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def load_chunks(self) -> List[Dict]:
        """Load all chunks from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT chunk_id,
                              title,
                              content,
                              level,
                              section_number,
                              chunk_type,
                              has_tables,
                              content_length,
                              preprocessed_text,
                              tokens,
                              domain_features
                       FROM chunks
                       ORDER BY id
                       ''')

        chunks = []
        for row in cursor.fetchall():
            chunk_data = {
                'chunk_id': row[0],
                'title': row[1],
                'content': row[2],
                'level': row[3],
                'section_number': row[4],
                'chunk_type': row[5],
                'has_tables': row[6],
                'content_length': row[7],
                'preprocessed_text': row[8],
                'tokens': json.loads(row[9]),
                'domain_features': json.loads(row[10])
            }
            chunks.append(chunk_data)

        conn.close()
        return chunks

    def save_search_index(self, index_name: str, index_data: Any):
        """Save search index (BM25, TF-IDF) to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            serialized_data = pickle.dumps(index_data)
            cursor.execute('''
            INSERT OR REPLACE INTO search_indices 
            (index_name, index_data, updated_at)
            VALUES (?, ?, ?)
            ''', (index_name, serialized_data, datetime.now().isoformat()))

            conn.commit()

        except Exception as e:
            print(f"Error saving search index {index_name}: {str(e)}")
        finally:
            conn.close()

    def load_search_index(self, index_name: str) -> Any:
        """Load search index from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
                       SELECT index_data
                       FROM search_indices
                       WHERE index_name = ?
                       ''', (index_name,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return pickle.loads(result[0])
        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('SELECT COUNT(*) FROM chunks')
        chunk_count = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM search_indices')
        index_count = cursor.fetchone()[0]

        cursor.execute('SELECT MIN(created_at), MAX(updated_at) FROM chunks')
        dates = cursor.fetchone()

        conn.close()

        return {
            'total_chunks': chunk_count,
            'search_indices': index_count,
            'first_created': dates[0],
            'last_updated': dates[1],
            'database_file': self.db_path
        }

    def search_fts(self, query: str, limit: int = 10) -> List[str]:
        """Full-text search using SQLite FTS"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Simple FTS query
        cursor.execute('''
                       SELECT chunk_id
                       FROM chunks_fts
                       WHERE chunks_fts MATCH ?
                       ORDER BY rank LIMIT ?
                       ''', (query, limit))

        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        return results

    def _generate_chunk_hash(self, chunk) -> str:
        """Generate unique hash for chunk"""
        content = f"{chunk.title}{chunk.content}{chunk.level}{chunk.section_number}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()[:8]

    def clear_database(self):
        """Clear all data from database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM chunks')
        cursor.execute('DELETE FROM chunks_fts')
        cursor.execute('DELETE FROM search_indices')

        conn.commit()
        conn.close()
        print("Database cleared")


class AzerbaijaniTextProcessor:
    """Enhanced text processor for Azerbaijani language"""

    def __init__(self):
        # Azerbaijani stopwords
        self.stopwords = {
            'və', 'ilə', 'da', 'də', 'ki', 'bu', 'o', 'bir', 'daha', 'üçün',
            'olan', 'olub', 'olaraq', 'həmin', 'onun', 'bunun', 'sonra',
            'əvvəl', 'kimi', 'qədər', 'tərəfindən', 'əsasında', 'çərçivəsində',
            'nəticəsində', 'məqsədilə', 'vasitəsilə', 'həyata', 'keçirilməsi',
            'edilməsi', 'olunması', 'çox', 'az', 'böyük', 'kiçik', 'yaxşı',
            'pis', 'yeni', 'köhnə', 'hər', 'bütün', 'digər', 'başqa'
        }

    def tokenize(self, text: str) -> List[str]:
        """Tokenize text for BM25 processing"""
        # Convert to lowercase
        text = text.lower()

        # Remove punctuation and special characters
        text = re.sub(r'[^\w\səüöğışç]', ' ', text)

        # Split into words
        words = text.split()

        # Filter stopwords and short words
        tokens = [word for word in words if word not in self.stopwords and len(word) > 2]

        return tokens

    def preprocess_text(self, text: str) -> str:
        """Preprocess text for TF-IDF vectorization"""
        tokens = self.tokenize(text)
        return ' '.join(tokens)

    def extract_domain_features(self, text: str) -> Dict[str, float]:
        """Extract domain-specific features with weights"""
        features = defaultdict(float)
        text_lower = text.lower()

        # Strategy-related terms
        strategy_terms = ['strategiya', 'plan', 'məqsəd', 'hədəf', 'prioritet', 'istiqamət']
        for term in strategy_terms:
            if term in text_lower:
                features['strategy_score'] += 1.0

        # Digital economy terms
        digital_terms = ['rəqəmsal', 'texnologiya', 'innovasiya', 'süni', 'intellekt', 'transformasiya']
        for term in digital_terms:
            if term in text_lower:
                features['digital_score'] += 1.0

        # Government/policy terms
        gov_terms = ['dövlət', 'nazirlik', 'qurum', 'qanun', 'qərar', 'sərəncam']
        for term in gov_terms:
            if term in text_lower:
                features['government_score'] += 1.0

        # Economic terms
        econ_terms = ['iqtisadiyyat', 'iqtisadi', 'maliyyə', 'investisiya', 'biznes', 'artım']
        for term in econ_terms:
            if term in text_lower:
                features['economy_score'] += 1.0

        return dict(features)


class ChunkObject:
    """Chunk object that can be created from database data or JSON data"""

    def __init__(self, chunk_data: Dict = None, title: str = "", content: str = "",
                 level: int = 0, section_number: str = "", chunk_type: str = "content",
                 tables: List = None):
        if chunk_data and isinstance(chunk_data, dict):
            # From database or JSON
            self.chunk_id = chunk_data.get('chunk_id')
            self.title = chunk_data.get('title', title)
            self.content = chunk_data.get('content', content)
            self.level = chunk_data.get('level', level)
            self.section_number = chunk_data.get('section_number', section_number)
            self.chunk_type = chunk_data.get('chunk_type', chunk_type)
            self.tables = chunk_data.get('tables', tables or [])
            if isinstance(self.tables, dict):
                self.tables = [self.tables]  # Convert single table dict to list
        else:
            # Direct initialization
            self.chunk_id = None
            self.title = title
            self.content = content
            self.level = level
            self.section_number = section_number
            self.chunk_type = chunk_type
            self.tables = tables or []


class JSONChunkLoader:
    """Load chunks from JSON file and convert to ChunkObject instances"""

    def __init__(self, json_file_path: str):
        self.json_file_path = json_file_path
        self.chunks_data = self._load_json()

    def _load_json(self):
        """Load and parse the JSON file"""
        try:
            with open(self.json_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: JSON file not found at {self.json_file_path}")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            return {}

    def create_chunk_objects(self):
        """Convert JSON data to ChunkObject instances"""
        chunks = []

        for chunk_id, chunk_data in self.chunks_data.items():
            # Extract section level from content structure
            level = 0
            if '5.1' in chunk_id or '5.2' in chunk_id:
                level = 2
            elif chunk_id.startswith('5'):
                level = 1

            # Create chunk object
            chunk = ChunkObject(
                title=chunk_data.get('title', ''),
                content=chunk_data.get('content', ''),
                level=level,
                section_number=chunk_id,
                chunk_type='content',
                tables=chunk_data.get('tables', [])
            )
            chunks.append(chunk)

        return chunks


class HybridSearchEngine:
    """Enhanced hybrid search with SQLite database persistence and JSON integration"""

    def __init__(self, chunks: List = None, text_processor: AzerbaijaniTextProcessor = None,
                 db_path: str = "azerbaijani_chunks.db", force_rebuild: bool = False,
                 json_file_path: str = None):
        self.text_processor = text_processor or AzerbaijaniTextProcessor()
        self.db = DatabaseManager(db_path)

        # Initialize storage
        self.chunks = []
        self.chunk_texts = []
        self.chunk_tokens = []
        self.chunk_features = []
        self.bm25 = None
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None

        # Load chunks from JSON if provided
        if json_file_path and os.path.exists(json_file_path):
            print(f"Loading chunks from JSON file: {json_file_path}")
            loader = JSONChunkLoader(json_file_path)
            if loader.chunks_data:
                json_chunks = loader.create_chunk_objects()
                if chunks:
                    chunks.extend(json_chunks)
                else:
                    chunks = json_chunks
                print(f"Loaded {len(json_chunks)} chunks from JSON")

        # Load or build search data
        if force_rebuild or self._should_rebuild_indices():
            if chunks:
                print("Building new search indices from provided chunks...")
                self._build_from_chunks(chunks)
            else:
                print("No chunks provided for rebuild")
        else:
            print("Loading existing search indices from database...")
            self._load_from_database()

        print(f"Search engine initialized with {len(self.chunks)} chunks")

    def _should_rebuild_indices(self) -> bool:
        """Check if search indices need to be rebuilt"""
        stats = self.db.get_stats()
        if stats['total_chunks'] == 0:
            return True

        # Check if BM25 and TF-IDF indices exist
        bm25_exists = self.db.load_search_index('bm25') is not None
        tfidf_exists = self.db.load_search_index('tfidf_vectorizer') is not None

        return not (bm25_exists and tfidf_exists)

    def _build_from_chunks(self, chunks: List):
        """Build search indices from chunk objects and save to database"""
        print("Processing and storing chunks...")

        # Clear existing data
        self.db.clear_database()

        for i, chunk in enumerate(chunks):
            # Process chunk
            combined_text = f"{chunk.title} {chunk.content}"
            preprocessed_text = self.text_processor.preprocess_text(combined_text)
            tokens = self.text_processor.tokenize(combined_text)
            features = self.text_processor.extract_domain_features(combined_text)

            # Save to database
            chunk_id = self.db.save_chunk(chunk, i, preprocessed_text, tokens, features)

            if chunk_id:
                # Store for search indices
                self.chunks.append(ChunkObject(chunk.__dict__ if hasattr(chunk, '__dict__') else vars(chunk)))
                self.chunk_texts.append(preprocessed_text)
                self.chunk_tokens.append(tokens)
                self.chunk_features.append(features)

        # Build and save search indices
        self._build_search_indices()
        self._save_search_indices()

        print(f"Stored {len(self.chunks)} chunks in database")

    def _load_from_database(self):
        """Load chunks and search indices from database"""
        # Load chunk data
        chunk_data_list = self.db.load_chunks()

        for chunk_data in chunk_data_list:
            self.chunks.append(ChunkObject(chunk_data))
            self.chunk_texts.append(chunk_data['preprocessed_text'])
            self.chunk_tokens.append(chunk_data['tokens'])
            self.chunk_features.append(chunk_data['domain_features'])

        # Load search indices
        self.bm25 = self.db.load_search_index('bm25')
        tfidf_data = self.db.load_search_index('tfidf_vectorizer')

        if tfidf_data:
            self.tfidf_vectorizer = tfidf_data['vectorizer']
            self.tfidf_matrix = tfidf_data['matrix']

        # Rebuild indices if not found or corrupted
        if not self.bm25 or not self.tfidf_vectorizer:
            print("Search indices missing or corrupted, rebuilding...")
            self._build_search_indices()
            self._save_search_indices()

    def _build_search_indices(self):
        """Build BM25 and TF-IDF search indices"""
        if not self.chunk_tokens:
            print("No tokens available for building search indices")
            return

        print("Building BM25 index...")
        self.bm25 = BM25Okapi(self.chunk_tokens)

        print("Building TF-IDF index...")
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
            stop_words=None
        )
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(self.chunk_texts)

    def _save_search_indices(self):
        """Save search indices to database"""
        print("Saving search indices to database...")

        if self.bm25:
            self.db.save_search_index('bm25', self.bm25)

        if self.tfidf_vectorizer and self.tfidf_matrix is not None:
            tfidf_data = {
                'vectorizer': self.tfidf_vectorizer,
                'matrix': self.tfidf_matrix
            }
            self.db.save_search_index('tfidf_vectorizer', tfidf_data)

    def add_chunks(self, new_chunks: List):
        """Add new chunks to existing search engine"""
        print(f"Adding {len(new_chunks)} new chunks...")

        current_count = len(self.chunks)

        for i, chunk in enumerate(new_chunks):
            chunk_index = current_count + i

            # Process chunk
            combined_text = f"{chunk.title} {chunk.content}"
            preprocessed_text = self.text_processor.preprocess_text(combined_text)
            tokens = self.text_processor.tokenize(combined_text)
            features = self.text_processor.extract_domain_features(combined_text)

            # Save to database
            chunk_id = self.db.save_chunk(chunk, chunk_index, preprocessed_text, tokens, features)

            if chunk_id:
                # Add to search data
                self.chunks.append(ChunkObject(chunk.__dict__ if hasattr(chunk, '__dict__') else vars(chunk)))
                self.chunk_texts.append(preprocessed_text)
                self.chunk_tokens.append(tokens)
                self.chunk_features.append(features)

        # Rebuild search indices
        self._build_search_indices()
        self._save_search_indices()

        print(f"Added {len(new_chunks)} chunks. Total: {len(self.chunks)}")

    def load_from_json(self, json_file_path: str, force_rebuild: bool = True):
        """Load chunks from JSON file"""
        if not os.path.exists(json_file_path):
            print(f"JSON file not found: {json_file_path}")
            return False

        loader = JSONChunkLoader(json_file_path)
        if not loader.chunks_data:
            print("No data loaded from JSON file")
            return False

        chunks = loader.create_chunk_objects()
        print(f"Loaded {len(chunks)} chunks from JSON")

        if force_rebuild:
            self._build_from_chunks(chunks)
        else:
            self.add_chunks(chunks)

        return True

    def search(self, query: str, top_k: int = 5,
               search_type: str = 'hybrid',
               level_filter: Optional[int] = None,
               chunk_type_filter: Optional[str] = None) -> List[Tuple[Any, float, Dict]]:
        """
        Search using BM25, TF-IDF, and domain features

        Args:
            query: Search query
            top_k: Number of results to return
            search_type: 'bm25', 'tfidf', 'fts', or 'hybrid'
            level_filter: Filter by chunk level
            chunk_type_filter: Filter by chunk type

        Returns:
            List of (chunk, combined_score, score_details) tuples
        """
        if not self.chunks:
            return []

        # Tokenize query for BM25
        query_tokens = self.text_processor.tokenize(query)
        query_features = self.text_processor.extract_domain_features(query)

        results = []

        for i, chunk in enumerate(self.chunks):
            # Apply filters
            if level_filter is not None and chunk.level != level_filter:
                continue
            if chunk_type_filter is not None and chunk.chunk_type != chunk_type_filter:
                continue

            # Calculate different similarity scores
            scores = {}

            if search_type in ['bm25', 'hybrid'] and self.bm25:
                # BM25 score
                bm25_score = self.bm25.get_scores(query_tokens)[i]
                scores['bm25'] = float(bm25_score)

            if search_type in ['tfidf', 'hybrid'] and self.tfidf_vectorizer:
                # TF-IDF cosine similarity
                query_processed = self.text_processor.preprocess_text(query)
                query_vector = self.tfidf_vectorizer.transform([query_processed])
                tfidf_score = cosine_similarity(query_vector, self.tfidf_matrix[i])[0][0]
                scores['tfidf'] = float(tfidf_score)

            if search_type == 'fts':
                # Use SQLite FTS for simple text matching
                fts_results = self.db.search_fts(query, top_k * 2)
                scores['fts'] = 1.0 if chunk.chunk_id in fts_results else 0.0

            # Domain feature matching
            feature_score = self._calculate_feature_similarity(query_features, self.chunk_features[i])
            scores['feature'] = feature_score

            # Hierarchical boost
            hierarchy_boost = self._calculate_hierarchy_boost(chunk)
            scores['hierarchy'] = hierarchy_boost

            # Calculate combined score
            combined_score = self._calculate_combined_score(scores, search_type)

            if combined_score > 0.01:  # Minimum threshold
                results.append((chunk, combined_score, scores))

        # Sort by combined score and return top_k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def _calculate_combined_score(self, scores: Dict[str, float], search_type: str) -> float:
        """Calculate combined score based on search type"""
        if search_type == 'hybrid':
            weights = {
                'bm25': 0.4,
                'tfidf': 0.4,
                'feature': 0.15,
                'hierarchy': 0.05
            }
            combined_score = sum(weights.get(key, 0) * score for key, score in scores.items())

        elif search_type == 'bm25':
            combined_score = scores.get('bm25', 0) + 0.1 * scores.get('feature', 0)

        elif search_type == 'tfidf':
            combined_score = scores.get('tfidf', 0) + 0.1 * scores.get('feature', 0)

        elif search_type == 'fts':
            combined_score = scores.get('fts', 0) + 0.2 * scores.get('feature', 0)

        else:
            combined_score = sum(scores.values()) / len(scores) if scores else 0

        return combined_score

    def _calculate_feature_similarity(self, query_features: Dict[str, float],
                                      chunk_features: Dict[str, float]) -> float:
        """Calculate similarity based on domain features"""
        if not query_features or not chunk_features:
            return 0.0

        # Calculate cosine similarity between feature vectors
        query_vec = np.array([query_features.get(key, 0) for key in
                              ['strategy_score', 'digital_score', 'government_score', 'economy_score']])
        chunk_vec = np.array([chunk_features.get(key, 0) for key in
                              ['strategy_score', 'digital_score', 'government_score', 'economy_score']])

        # Avoid division by zero
        query_norm = np.linalg.norm(query_vec)
        chunk_norm = np.linalg.norm(chunk_vec)

        if query_norm == 0 or chunk_norm == 0:
            return 0.0

        similarity = np.dot(query_vec, chunk_vec) / (query_norm * chunk_norm)
        return float(similarity)

    def _calculate_hierarchy_boost(self, chunk) -> float:
        """Calculate boost based on chunk hierarchy position"""
        level_boosts = {0: 1.0, 1: 0.8, 2: 0.6, 3: 0.4, 4: 0.2}
        base_boost = level_boosts.get(chunk.level, 0.1)
        table_boost = 0.2 if chunk.tables else 0.0
        return base_boost + table_boost

    def get_search_explanation(self, query: str, chunk, scores: Dict) -> str:
        """Generate explanation for why a chunk was returned"""
        explanations = []

        if scores.get('bm25', 0) > 0.5:
            explanations.append(f"Güclü açar söz uyğunluğu (BM25: {scores['bm25']:.3f})")

        if scores.get('tfidf', 0) > 0.1:
            explanations.append(f"Mətn oxşarlığı (TF-IDF: {scores['tfidf']:.3f})")

        if scores.get('feature', 0) > 0.3:
            explanations.append(f"Sahə terminləri uyğunluğu ({scores['feature']:.3f})")

        if chunk.level == 0:
            explanations.append("Əsas bölmə")

        if chunk.tables:
            explanations.append("Cədvəl məlumatları mövcud")

        return "; ".join(explanations) if explanations else "Ümumi məzmun uyğunluğu"

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database and search engine statistics"""
        db_stats = self.db.get_stats()

        search_stats = {
            'chunks_in_memory': len(self.chunks),
            'bm25_ready': self.bm25 is not None,
            'tfidf_ready': self.tfidf_vectorizer is not None,
            'vocabulary_size': len(self.tfidf_vectorizer.vocabulary_) if self.tfidf_vectorizer else 0
        }

        return {**db_stats, **search_stats}


# Example usage and testing
if __name__ == "__main__":

    print("Azerbaijani Hybrid Search Engine with JSON Integration")
    print("=" * 70)

    # Check if chunk.json exists
    json_file = "chunk.json"
    if os.path.exists(json_file):
        print(f"Found {json_file}, loading chunks...")

        # Initialize search engine with JSON data
        search_engine = HybridSearchEngine(
            json_file_path=json_file,
            db_path="azerbaijani_chunks.db",
            force_rebuild=True
        )

        # Show database stats
        stats = search_engine.get_database_stats()
        print("\nDATABASE STATISTICS:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Test search functionality
        test_queries = [
            "rəqəmsal iqtisadiyyat",
            "strategiya",
            "biznes",
            "investisiya",
            "texnologiya",
            "məqsədlər",
            "prioritet istiqamətlər"
        ]

        print(f"\nTESTING SEARCH FUNCTIONALITY")
        print("-" * 50)

        for query in test_queries:
            print(f"\nQuery: '{query}'")
            print("-" * 30)

            results = search_engine.search(query, top_k=3, search_type='hybrid')

            if results:
                for i, (chunk, score, score_details) in enumerate(results, 1):
                    print(f"{i}. {chunk.title}")
                    print(f"   Score: {score:.4f}")
                    print(f"   Section: {chunk.section_number}")
                    # Show first 100 characters of content
                    content_preview = chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content
                    print(f"   Content: {content_preview}")

                    # Get explanation
                    explanation = search_engine.get_search_explanation(query, chunk, score_details)
                    print(f"   Explanation: {explanation}")
                    print()
            else:
                print("   No results found.")

        print("\nJSON integration completed successfully!")
        print(f"Database saved to: azerbaijani_chunks.db")
        print("You can now search through your Azerbaijani content.")

    else:
        print(f"No {json_file} found. Creating sample data...")

        # Create some test chunks
        test_chunks = [
            ChunkObject(
                title="Rəqəmsal İqtisadiyyat Strategiyası",
                content="Rəqəmsal transformasiya prioritetləri və məqsədləri",
                level=0,
                section_number="1",
                chunk_type="section"
            ),
            ChunkObject(
                title="Maliyyə Mexanizmləri",
                content="İnvestisiya və maliyyələşdirmə yolları",
                level=1,
                section_number="1.1",
                chunk_type="section"
            ),
            ChunkObject(
                title="Texnoloji İnnovasiyalar",
                content="Süni intellekt və rəqəmsal həllər",
                level=2,
                section_number="1.1.1",
                chunk_type="content"
            ),
            ChunkObject(
                title="Dövlət Dəstəyi",
                content="Hökumət tərəfindən verilən maliyyə yardımı",
                level=1,
                section_number="1.2",
                chunk_type="section"
            ),
            ChunkObject(
                title="İnsan Kapitalı",
                content="Kadr hazırlığı və təhsil proqramları",
                level=2,
                section_number="1.2.1",
                chunk_type="content"
            )
        ]

        # Initialize search engine with test data
        search_engine = HybridSearchEngine(
            chunks=test_chunks,
            db_path="test_azerbaijani.db",
            force_rebuild=True
        )

        # Show database stats
        stats = search_engine.get_database_stats()
        print("\nDATABASE STATISTICS:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        # Test search with sample data
        query = "rəqəmsal transformasiya strategiyası"
        print(f"\nSEARCH QUERY: {query}")
        print("-" * 50)

        results = search_engine.search(query, top_k=3, search_type='hybrid')

        for i, (chunk, score, score_details) in enumerate(results, 1):
            print(f"{i}. {chunk.title}")
            print(f"   Score: {score:.4f}")
            print(f"   Details: {score_details}")
            explanation = search_engine.get_search_explanation(query, chunk, score_details)
            print(f"   Explanation: {explanation}")
            print()

        print("\nTo use your JSON data:")
        print("1. Make sure 'chunk.json' is in the same directory")
        print("2. Run this script again")
        print("3. The system will automatically load your data")