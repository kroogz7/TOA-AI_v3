"""
TOA-AI Vector Indexer
Indexes document chunks for vector search
"""

import json
import os
import sys
from pathlib import Path
from tqdm import tqdm
import numpy as np

# Add parent directory to system path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.config import VECTOR_DB, INDEX_DIR, PROCESSED_DIR
from src.utils.logger import get_logger, timer

logger = get_logger("VectorIndexer")

class VectorIndexer:
    """
    Indexes document chunks for vector search
    """
    
    def __init__(self, collection_name=None):
        """
        Initialize the vector indexer
        
        Args:
            collection_name (str, optional): Name of the ChromaDB collection
        """
        self.collection_name = collection_name or VECTOR_DB["collection_name"]
        self.embedding_model_name = VECTOR_DB["embedding_model"]
        self.embedding_model = None
        self.chroma_client = None
        self.collection = None
    
    @timer
    def initialize_models(self):
        """Initialize embedding models and vector database"""
        try:
            # Import here to allow for dependency checks
            import chromadb
            from sentence_transformers import SentenceTransformer
            
            # Initialize embedding model
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            self.embedding_model = SentenceTransformer(self.embedding_model_name)
            
            # Initialize ChromaDB client
            logger.info(f"Initializing ChromaDB client")
            self.chroma_client = chromadb.PersistentClient(path=str(INDEX_DIR))
            
            # Get or create collection
            try:
                self.collection = self.chroma_client.get_collection(name=self.collection_name)
                logger.info(f"Using existing collection: {self.collection_name}")
            except:
                logger.info(f"Creating new collection: {self.collection_name}")
                self.collection = self.chroma_client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "TOA-AI Technical Order chunks"}
                )
            
            return True
        except Exception as e:
            logger.error(f"Error initializing models: {str(e)}")
            return False
    
    @timer
    def index_chunks(self, chunks=None, chunks_path=None):
        """
        Index document chunks
        
        Args:
            chunks (list, optional): List of chunks to index
            chunks_path (str, optional): Path to chunks JSON file
            
        Returns:
            bool: True if indexing was successful
        """
        if not self.embedding_model or not self.collection:
            success = self.initialize_models()
            if not success:
                return False
        
        # Load chunks if not provided
        if not chunks and chunks_path:
            try:
                with open(chunks_path, "r") as f:
                    chunks = json.load(f)
            except Exception as e:
                logger.error(f"Error loading chunks from {chunks_path}: {str(e)}")
                return False
        elif not chunks:
            # Try to load all chunks from default location
            all_chunks_path = PROCESSED_DIR / "all_chunks.json"
            try:
                with open(all_chunks_path, "r") as f:
                    chunks = json.load(f)
            except Exception as e:
                logger.error(f"Error loading chunks from {all_chunks_path}: {str(e)}")
                return False
        
        if not chunks:
            logger.error("No chunks to index")
            return False
        
        logger.info(f"Indexing {len(chunks)} chunks")
        
        # Prepare batch data
        chunk_ids = []
        chunk_texts = []
        chunk_metadatas = []
        
        for chunk in chunks:
            chunk_ids.append(chunk["id"])
            chunk_texts.append(chunk["content"])
            
            # Convert asset lists to comma-separated strings for ChromaDB
            metadata = chunk["metadata"].copy()
            for asset_type in ["images", "tables", "warnings"]:
                if asset_type in metadata and isinstance(metadata[asset_type], list):
                    metadata[asset_type] = ",".join(metadata[asset_type])
            
            chunk_metadatas.append(metadata)
        
        # Generate embeddings
        logger.info("Generating embeddings")
        embeddings = []
        
        # Process in batches to avoid memory issues
        batch_size = 32
        for i in tqdm(range(0, len(chunk_texts), batch_size), desc="Generating embeddings"):
            batch_texts = chunk_texts[i:i+batch_size]
            batch_embeddings = self.embedding_model.encode(batch_texts)
            embeddings.extend(batch_embeddings.tolist())
        
        # Add to collection
        logger.info("Adding to vector database")
        
        # Process in batches
        for i in tqdm(range(0, len(chunk_ids), batch_size), desc="Adding to database"):
            self.collection.add(
                ids=chunk_ids[i:i+batch_size],
                embeddings=embeddings[i:i+batch_size],
                documents=chunk_texts[i:i+batch_size],
                metadatas=chunk_metadatas[i:i+batch_size]
            )
        
        # Get collection stats
        collection_count = self.collection.count()
        logger.info(f"Indexing complete. Collection now has {collection_count} documents")
        
        return True
    
    @timer
    def search(self, query, top_k=None, filter_dict=None):
        """
        Search for chunks matching a query
        
        Args:
            query (str): Query text
            top_k (int, optional): Number of results to return
            filter_dict (dict, optional): Metadata filters
            
        Returns:
            dict: Search results
        """
        if not self.embedding_model or not self.collection:
            success = self.initialize_models()
            if not success:
                return None
        
        if not top_k:
            top_k = VECTOR_DB["top_k"]
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode(query).tolist()
        
        # Perform search
        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=filter_dict
            )
            
            return results
        except Exception as e:
            logger.error(f"Error searching: {str(e)}")
            return None
    
    @timer
    def hybrid_search(self, query, top_k=None, filter_dict=None):
        """
        Perform hybrid search (vector + keyword)
        
        Args:
            query (str): Query text
            top_k (int, optional): Number of results to return
            filter_dict (dict, optional): Metadata filters
            
        Returns:
            dict: Search results
        """
        # This is a simplified hybrid search
        # In a real implementation, we would combine BM25 with vector search
        
        # For now, just use vector search
        return self.search(query, top_k, filter_dict)
    
    def reset_index(self):
        """Reset the index (delete and recreate collection)"""
        if not self.chroma_client:
            self.initialize_models()
        
        try:
            self.chroma_client.delete_collection(name=self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
            
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "TOA-AI Technical Order chunks"}
            )
            logger.info(f"Created new collection: {self.collection_name}")
            
            return True
        except Exception as e:
            logger.error(f"Error resetting index: {str(e)}")
            return False 