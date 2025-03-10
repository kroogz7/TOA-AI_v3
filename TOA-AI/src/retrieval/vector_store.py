import os
import json
import numpy as np
import faiss
import logging
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
import re
import time
from functools import wraps

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def timer(func):
    """Decorator to time function execution"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logger.info(f"{func.__name__} completed in {end_time - start_time:.2f} seconds")
        return result
    return wrapper

class VectorStore:
    """Vector store for document chunks using FAISS and BM25"""
    
    def __init__(self, embeddings_path=None, model_name="all-MiniLM-L6-v2"):
        """
        Initialize the vector store
        
        Args:
            embeddings_path (str): Path to the embeddings file
            model_name (str): Name of the sentence transformer model
        """
        self.model_name = model_name
        self.model = None
        self.index = None
        self.chunks = []
        self.embeddings = None
        self.bm25 = None
        self.tokenized_corpus = None
        
        if embeddings_path:
            self.load_embeddings(embeddings_path)
    
    @timer
    def load_embeddings(self, embeddings_path):
        """
        Load embeddings and chunks from a file
        
        Args:
            embeddings_path (str): Path to the embeddings file
        """
        logger.info(f"Loading embeddings from {embeddings_path}")
        
        try:
            with open(embeddings_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.embeddings = np.array(data["embeddings"])
            self.chunks = data["chunks"]
            
            logger.info(f"Loaded {len(self.chunks)} chunks with embeddings shape {self.embeddings.shape}")
            
            # Initialize FAISS index
            self._create_index()
            
            # Initialize BM25
            self._initialize_bm25()
            
            return True
        except Exception as e:
            logger.error(f"Error loading embeddings: {e}")
            return False
    
    def _create_index(self):
        """Create the FAISS index from embeddings"""
        logger.info("Creating FAISS index")
        
        # Get the dimension of the embeddings
        dimension = self.embeddings.shape[1]
        
        # Create a new index: IndexFlatL2 for exact search with L2 distance
        self.index = faiss.IndexFlatL2(dimension)
        
        # Add the embeddings to the index
        self.index.add(self.embeddings.astype(np.float32))
        
        logger.info(f"Created FAISS index with {self.index.ntotal} vectors")
    
    def _initialize_bm25(self):
        """Initialize BM25 for lexical search"""
        logger.info("Initializing BM25 for lexical search")
        
        # Tokenize the content of each chunk
        self.tokenized_corpus = [self._tokenize(chunk["content"]) for chunk in self.chunks]
        
        # Create BM25 object
        self.bm25 = BM25Okapi(self.tokenized_corpus)
        
        logger.info("BM25 initialized successfully")
    
    def _tokenize(self, text):
        """
        Tokenize text for BM25
        
        Args:
            text (str): Text to tokenize
            
        Returns:
            list: List of tokens
        """
        # Simple tokenization: lowercase, remove punctuation, split on whitespace
        text = text.lower()
        text = re.sub(r'[^\w\s]', ' ', text)
        return text.split()
    
    @timer
    def search(self, query, k=5, alpha=0.5):
        """
        Hybrid search combining FAISS (semantic) and BM25 (lexical)
        
        Args:
            query (str): Search query
            k (int): Number of results to return
            alpha (float): Weight for semantic search (1-alpha for lexical)
            
        Returns:
            list: List of (chunk, score) tuples
        """
        if not self.index or not self.bm25:
            logger.error("Vector store not initialized")
            return []
        
        # Initialize model if not already done
        if not self.model:
            logger.info(f"Loading model {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
        
        # Get query embedding
        query_embedding = self.model.encode([query])[0]
        
        # Semantic search with FAISS
        semantic_k = min(k * 2, len(self.chunks))  # Get more results than needed
        distances, indices = self.index.search(
            np.array([query_embedding]).astype(np.float32), 
            semantic_k
        )
        
        # Normalize semantic scores (convert distances to similarities)
        max_dist = np.max(distances[0]) + 1e-6  # Add small value to avoid division by zero
        semantic_scores = np.array([1.0 - (dist / max_dist) for dist in distances[0]])
        
        # Lexical search with BM25
        tokenized_query = self._tokenize(query)
        bm25_scores = np.array(self.bm25.get_scores(tokenized_query))
        
        # Normalize BM25 scores
        max_bm25 = np.max(bm25_scores) + 1e-6  # Add small value to avoid division by zero
        bm25_scores = bm25_scores / max_bm25
        
        # Combine scores for the top semantic results
        combined_results = []
        seen_ids = set()
        
        for i, idx in enumerate(indices[0]):
            chunk = self.chunks[idx]
            chunk_id = chunk["id"]
            
            if chunk_id in seen_ids:
                continue
            seen_ids.add(chunk_id)
            
            semantic_score = semantic_scores[i]
            bm25_score = bm25_scores[idx]
            
            # Hybrid score
            hybrid_score = (alpha * semantic_score) + ((1 - alpha) * bm25_score)
            
            combined_results.append((chunk, hybrid_score))
        
        # Sort by combined score and return top k
        combined_results.sort(key=lambda x: x[1], reverse=True)
        return combined_results[:k]
    
    def search_by_metadata(self, **kwargs):
        """
        Search chunks by metadata fields
        
        Args:
            **kwargs: Metadata key-value pairs to match
            
        Returns:
            list: List of matching chunks
        """
        results = []
        
        for chunk in self.chunks:
            metadata = chunk.get("metadata", {})
            match = True
            
            for key, value in kwargs.items():
                if key not in metadata or metadata[key] != value:
                    match = False
                    break
            
            if match:
                results.append(chunk)
                
        return results
    
    def save(self, output_path):
        """
        Save the vector store to disk
        
        Args:
            output_path (str): Directory to save the vector store
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            os.makedirs(output_path, exist_ok=True)
            
            # Save chunks
            chunks_path = os.path.join(output_path, "chunks.json")
            with open(chunks_path, 'w', encoding='utf-8') as f:
                json.dump(self.chunks, f)
            
            # Save FAISS index
            index_path = os.path.join(output_path, "index.faiss")
            faiss.write_index(self.index, index_path)
            
            # Save tokenized corpus for BM25
            corpus_path = os.path.join(output_path, "tokenized_corpus.json")
            with open(corpus_path, 'w', encoding='utf-8') as f:
                json.dump(self.tokenized_corpus, f)
            
            # Save embeddings as NumPy file for compatibility
            if self.embeddings is not None:
                embeddings_path = os.path.join(output_path, "embeddings.npy")
                np.save(embeddings_path, self.embeddings)
            
            logger.info(f"Vector store saved to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving vector store: {e}")
            return False
    
    @classmethod
    def load(cls, input_path, model_name="all-MiniLM-L6-v2"):
        """
        Load a vector store from disk
        
        Args:
            input_path (str): Directory containing the vector store
            model_name (str): Name of the sentence transformer model
            
        Returns:
            VectorStore: Loaded vector store
        """
        try:
            vs = cls(model_name=model_name)
            
            # Load chunks
            chunks_path = os.path.join(input_path, "chunks.json")
            with open(chunks_path, 'r', encoding='utf-8') as f:
                vs.chunks = json.load(f)
            
            # Load FAISS index
            index_path = os.path.join(input_path, "index.faiss")
            vs.index = faiss.read_index(index_path)
            
            # Load tokenized corpus for BM25
            corpus_path = os.path.join(input_path, "tokenized_corpus.json")
            with open(corpus_path, 'r', encoding='utf-8') as f:
                vs.tokenized_corpus = json.load(f)
            
            # Initialize BM25
            vs.bm25 = BM25Okapi(vs.tokenized_corpus)
            
            # Load embeddings directly from file instead of extracting from FAISS
            # This is more compatible across different FAISS versions
            embeddings_path = os.path.join(input_path, "embeddings.npy")
            if os.path.exists(embeddings_path):
                vs.embeddings = np.load(embeddings_path)
            else:
                # If embeddings file doesn't exist, create a dummy embeddings array
                # This is not ideal but allows the system to function
                logger.warning("Embeddings file not found, creating dummy embeddings")
                dim = vs.index.d
                vs.embeddings = np.zeros((len(vs.chunks), dim), dtype=np.float32)
            
            logger.info(f"Loaded vector store from {input_path} with {len(vs.chunks)} chunks")
            return vs
        except Exception as e:
            import traceback
            logger.error(f"Error loading vector store: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None 