"""
TOA-AI Chatbot
Combines retrieval and generation for a complete chatbot
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent directory to system path
sys.path.append(str(Path(__file__).parent.parent.parent))
from src.processors.vector_indexer import VectorIndexer
from src.chatbot.llm_service import LLMService
from src.utils.logger import get_logger, timer

logger = get_logger("TOAChatbot")

class TOAChatbot:
    """
    Technical Order Assistant Chatbot
    Combines retrieval and generation for a complete chatbot
    """
    
    def __init__(self, api_key=None):
        """
        Initialize the TOA chatbot
        
        Args:
            api_key (str, optional): OpenAI API key
        """
        # Initialize vector indexer
        self.vector_indexer = VectorIndexer()
        success = self.vector_indexer.initialize_models()
        if not success:
            logger.error("Failed to initialize vector indexer")
        
        # Initialize LLM service
        self.llm_service = LLMService(api_key=api_key)
        
        # Initialize conversation history
        self.conversation_history = []
    
    @timer
    def answer_query(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Answer a user query
        
        Args:
            query (str): User query
            top_k (int): Number of chunks to retrieve
            
        Returns:
            Dict: Response object with answer and sources
        """
        # Retrieve relevant chunks
        retrieval_results = self.retrieve_context(query, top_k)
        
        # Check if retrieval was successful
        if not retrieval_results or not retrieval_results.get("chunks"):
            return {
                "answer": "I'm sorry, I couldn't find relevant information for your query.",
                "sources": [],
                "success": False
            }
        
        # Generate response using LLM
        response_text = self.llm_service.generate_response(
            query=query,
            context=retrieval_results["chunks"]
        )
        
        # Format sources for citation
        sources = self._format_sources(retrieval_results["chunks"])
        
        # Save to conversation history
        self.conversation_history.append({
            "query": query,
            "response": response_text,
            "sources": sources
        })
        
        return {
            "answer": response_text,
            "sources": sources,
            "success": True
        }
    
    @timer
    def retrieve_context(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """
        Retrieve context chunks for a query
        
        Args:
            query (str): User query
            top_k (int): Number of chunks to retrieve
            
        Returns:
            Dict: Retrieval results with chunks and metadata
        """
        # First, prioritize warnings if query indicates safety concerns
        safety_terms = ["safety", "warning", "caution", "danger", "hazard", "precaution", 
                       "careful", "protect", "prevent", "risk", "injury", "accident"]
        
        filter_dict = None
        if any(term in query.lower() for term in safety_terms):
            # Try to get chunks with warnings first
            filter_dict = {"contains_warning": True}
            
            results = self.vector_indexer.search(query, top_k=min(3, top_k), filter_dict=filter_dict)
            
            # If no warning chunks found, fall back to regular search
            if not results or len(results["ids"][0]) == 0:
                filter_dict = None
        
        # Perform vector search
        results = self.vector_indexer.search(query, top_k=top_k, filter_dict=filter_dict)
        
        if not results:
            return {"chunks": [], "success": False}
        
        # Process results into a usable format
        chunks = []
        
        for i in range(len(results["ids"][0])):
            chunk = {
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "score": results["distances"][0][i] if "distances" in results else None
            }
            chunks.append(chunk)
        
        return {
            "chunks": chunks,
            "success": True
        }
    
    def _format_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format source information for citations
        
        Args:
            chunks (List[Dict]): Retrieved chunks
            
        Returns:
            List[Dict]: Formatted sources
        """
        sources = []
        seen_sources = set()  # Track already processed sources to avoid duplicates
        
        for chunk in chunks:
            metadata = chunk.get("metadata", {})
            
            # Create a unique key for this source
            source_key = f"{metadata.get('document_id', '')}-{metadata.get('section_id', '')}"
            
            # Skip if we've already included this source
            if source_key in seen_sources:
                continue
                
            seen_sources.add(source_key)
            
            # Format the source
            source = {
                "document_id": metadata.get("document_id", "Unknown"),
                "to_number": metadata.get("to_number", "Unknown"),
                "section_id": metadata.get("section_id", "Unknown"),
                "section_title": metadata.get("section_title", ""),
                "page": metadata.get("page", "")
            }
            
            sources.append(source)
        
        return sources
    
    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Get the conversation history"""
        return self.conversation_history
    
    def clear_conversation_history(self) -> None:
        """Clear the conversation history"""
        self.conversation_history = [] 