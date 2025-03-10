import os
import logging
import time
from functools import wraps
from .vector_store import VectorStore
from sentence_transformers import SentenceTransformer

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

class Retriever:
    """Retriever for the RAG pipeline"""
    
    def __init__(self, vector_store_path=None, model_name="all-MiniLM-L6-v2"):
        """
        Initialize the retriever
        
        Args:
            vector_store_path (str): Path to the vector store directory
            model_name (str): Name of the sentence transformer model
        """
        self.vector_store = None
        
        if vector_store_path and os.path.exists(vector_store_path):
            self.load_vector_store(vector_store_path, model_name)
    
    def load_vector_store(self, vector_store_path, model_name="all-MiniLM-L6-v2"):
        """
        Load the vector store
        
        Args:
            vector_store_path (str): Path to the vector store directory
            model_name (str): Name of the sentence transformer model
            
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info(f"Loading vector store from {vector_store_path}")
        
        try:
            self.vector_store = VectorStore.load(vector_store_path, model_name)
            if self.vector_store:
                logger.info(f"Loaded vector store with {len(self.vector_store.chunks)} chunks")
                return True
            else:
                logger.error("Failed to load vector store")
                return False
        except Exception as e:
            logger.error(f"Error loading vector store: {e}")
            return False
    
    @timer
    def retrieve(self, query, k=5, alpha=0.5, include_metadata=True, filter_by=None):
        """
        Retrieve relevant chunks for a query
        
        Args:
            query (str): The query to retrieve chunks for
            k (int): Number of chunks to retrieve
            alpha (float): Weight for semantic search (1-alpha for lexical)
            include_metadata (bool): Whether to include metadata in the result
            filter_by (dict): Metadata filter criteria (e.g., {'document_id': 'TO 00-25-172CL-1'})
            
        Returns:
            list: List of retrieved chunks
        """
        if not self.vector_store:
            logger.error("Vector store not loaded")
            return []
        
        # First apply metadata filtering if requested
        filtered_chunks = None
        if filter_by:
            logger.info(f"Applying metadata filter: {filter_by}")
            filtered_chunks = self.vector_store.search_by_metadata(**filter_by)
            
            if not filtered_chunks:
                logger.warning(f"No chunks found matching filter criteria: {filter_by}")
                return []
            
            logger.info(f"Found {len(filtered_chunks)} chunks matching filter criteria")
            
            # Log some examples of the filtered chunks
            if len(filtered_chunks) > 0:
                for i, chunk in enumerate(filtered_chunks[:2]):
                    metadata = chunk.get('metadata', {})
                    logger.debug(f"Filtered chunk {i} example - ID: {chunk.get('id', 'Unknown')}, "
                               f"Document: {metadata.get('document_id', 'Unknown')}, "
                               f"Asset type: {metadata.get('asset_type', 'Unknown')}")
            
            # Create a temporary vector store with just the filtered chunks
            temp_store = VectorStore(model_name=self.vector_store.model_name)
            temp_store.chunks = filtered_chunks
            
            # We need to load the model to create embeddings for the filtered chunks
            if not temp_store.model:
                temp_store.model = self.vector_store.model if self.vector_store.model else SentenceTransformer(temp_store.model_name)
            
            # Extract text from chunks for embedding
            texts = [chunk.get('content', '') for chunk in filtered_chunks]
            
            # Create embeddings for the filtered chunks
            temp_store.embeddings = temp_store.model.encode(texts, convert_to_numpy=True)
            
            # Create index and BM25 for the filtered chunks
            temp_store._create_index()
            temp_store._initialize_bm25()
            
            # Search with the filtered store
            logger.info(f"Searching within {len(filtered_chunks)} filtered chunks using query: '{query}'")
            results = temp_store.search(query, k=min(k, len(filtered_chunks)), alpha=alpha)
        else:
            # No filtering, use the full vector store
            results = self.vector_store.search(query, k=k, alpha=alpha)
        
        # Format the results
        formatted_results = []
        for chunk, score in results:
            if include_metadata:
                formatted_results.append({
                    'content': chunk['content'],
                    'metadata': chunk['metadata'],
                    'score': score,
                    'id': chunk['id']
                })
            else:
                formatted_results.append({
                    'content': chunk['content'],
                    'score': score,
                    'id': chunk['id']
                })
        
        return formatted_results
    
    def format_retrieved_context(self, retrieved_chunks, max_tokens=4000):
        """
        Format retrieved chunks into a context string for the LLM
        
        Args:
            retrieved_chunks (list): List of retrieved chunks
            max_tokens (int): Maximum tokens for context
            
        Returns:
            str: Formatted context string
        """
        context = []
        
        for i, chunk in enumerate(retrieved_chunks):
            # Extract metadata for citation
            metadata = chunk.get('metadata', {})
            document_id = metadata.get('document_id', 'Unknown')
            page_num = metadata.get('page_num', 0) + 1  # Convert to 1-indexed for display
            asset_type = metadata.get('asset_type', 'content')
            
            # Format citation
            citation = f"[{document_id}, Page {page_num}, {asset_type.capitalize()}]"
            
            # Format content with citation
            formatted_chunk = f"CONTEXT ITEM {i+1} {citation}:\n{chunk['content']}\n"
            context.append(formatted_chunk)
        
        # Join all chunks
        context_str = "\n".join(context)
        
        # In a real implementation, you would truncate the context to max_tokens
        # This is a simplified implementation
        return context_str 