"""
TOA-AI LLM Service
Handles interaction with the LLM API
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent directory to system path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.config import LLM
from src.utils.logger import get_logger, timer

logger = get_logger("LLMService")

class LLMService:
    """
    Service for interacting with LLM APIs
    """
    
    def __init__(self, api_key=None, model=None):
        """
        Initialize the LLM service
        
        Args:
            api_key (str, optional): OpenAI API key (defaults to env var OPENAI_API_KEY)
            model (str, optional): Model to use (defaults to config)
        """
        # Set API key from environment if not provided
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("No OpenAI API key provided. Set OPENAI_API_KEY environment variable.")
        
        # Set model from config if not provided
        self.model = model or LLM["model"]
        self.temperature = LLM["temperature"]
        self.max_tokens = LLM["max_tokens"]
        self.system_prompt = LLM["system_prompt"]
        
        # Initialize OpenAI client
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the OpenAI client"""
        try:
            from openai import OpenAI
            
            self.client = OpenAI(api_key=self.api_key)
            logger.info(f"Initialized OpenAI client with model {self.model}")
            return True
        except ImportError:
            logger.error("OpenAI package not installed. Install with 'pip install openai'")
            return False
        except Exception as e:
            logger.error(f"Error initializing OpenAI client: {str(e)}")
            return False
    
    @timer
    def generate_response(self, 
                         query: str, 
                         context: List[Dict[str, Any]], 
                         system_prompt: Optional[str] = None) -> str:
        """
        Generate a response using the LLM
        
        Args:
            query (str): User query
            context (List[Dict]): Context chunks from retrieval
            system_prompt (str, optional): Custom system prompt
            
        Returns:
            str: Generated response
        """
        if not self.client:
            success = self._initialize_client()
            if not success:
                return "Error: LLM service not initialized properly."
        
        # Use custom system prompt if provided, otherwise use default
        system_prompt = system_prompt or self.system_prompt
        
        # Prepare context for the prompt
        context_str = self._format_context(context)
        
        try:
            # Create messages for the LLM
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context Information:\n{context_str}\n\nUser Query: {query}\n\nBased on the provided context, answer the user's query. Focus on accuracy and cite specific sections from the Technical Orders. If the information isn't in the context, say so."}
            ]
            
            # Call the API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            return f"Error generating response: {str(e)}"
    
    def _format_context(self, context: List[Dict[str, Any]]) -> str:
        """
        Format context chunks for the prompt
        
        Args:
            context (List[Dict]): Context chunks from retrieval
            
        Returns:
            str: Formatted context
        """
        formatted_context = ""
        
        # Add warnings first (prioritize safety information)
        warnings = [chunk for chunk in context if chunk.get("metadata", {}).get("chunk_type") == "warning"]
        if warnings:
            formatted_context += "SAFETY INFORMATION:\n"
            for warning in warnings:
                formatted_context += f"{warning['content']}\n\n"
        
        # Add other content
        formatted_context += "TECHNICAL INFORMATION:\n"
        for i, chunk in enumerate(context):
            # Skip warnings as they've already been included
            if chunk.get("metadata", {}).get("chunk_type") == "warning":
                continue
                
            # Include section info and content
            metadata = chunk.get("metadata", {})
            section_id = metadata.get("section_id", "Unknown Section")
            section_title = metadata.get("section_title", "")
            doc_id = metadata.get("document_id", "Unknown Document")
            page = metadata.get("page", "")
            
            formatted_context += f"[{doc_id} - Section {section_id}: {section_title} (Page {page})]\n"
            formatted_context += f"{chunk['content']}\n\n"
        
        return formatted_context 