import os
import logging
import json
from typing import Dict, List, Optional, Union, Any
from enum import Enum

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

class LLMProvider(str, Enum):
    """Enum for supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"

class LLMConnector:
    """
    Connector for LLM APIs (OpenAI and Anthropic)
    """
    
    def __init__(self, provider: str = None, model: str = None):
        """
        Initialize the LLM connector
        
        Args:
            provider (str): LLM provider (openai or anthropic)
            model (str): Model name
        """
        # Default provider is OpenAI if not specified
        self.provider = provider or os.environ.get("LLM_PROVIDER", LLMProvider.OPENAI)
        
        # Set default models based on provider
        if self.provider == LLMProvider.OPENAI:
            self.model = model or os.environ.get("OPENAI_MODEL", "gpt-4o")
            self.api_key = os.environ.get("OPENAI_API_KEY")
            if not self.api_key:
                logger.warning("OPENAI_API_KEY not found in environment variables")
        elif self.provider == LLMProvider.ANTHROPIC:
            self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-3-opus-20240229")
            self.api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not self.api_key:
                logger.warning("ANTHROPIC_API_KEY not found in environment variables")
        else:
            raise ValueError(f"Unsupported provider: {provider}. Use 'openai' or 'anthropic'")
        
        # Initialize client to None
        self.client = None
        
    def _initialize_client(self):
        """Initialize the appropriate client based on the provider"""
        if self.client:
            return
            
        if self.provider == LLMProvider.OPENAI:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
                logger.info(f"Initialized OpenAI client with model {self.model}")
            except ImportError:
                logger.error("OpenAI package not installed. Run: pip install openai")
                raise
        elif self.provider == LLMProvider.ANTHROPIC:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=self.api_key)
                logger.info(f"Initialized Anthropic client with model {self.model}")
            except ImportError:
                logger.error("Anthropic package not installed. Run: pip install anthropic")
                raise
                
    def generate_response(self, messages: List[Dict[str, str]], temperature: float = 0.2, 
                         max_tokens: int = 1000) -> str:
        """
        Generate a response from the LLM
        
        Args:
            messages (List[Dict]): List of message dictionaries with 'role' and 'content'
            temperature (float): Temperature parameter for generation
            max_tokens (int): Maximum tokens to generate
            
        Returns:
            str: Generated response
        """
        self._initialize_client()
        
        try:
            if self.provider == LLMProvider.OPENAI:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content
                
            elif self.provider == LLMProvider.ANTHROPIC:
                # Convert messages to Anthropic format
                system_message = next((msg["content"] for msg in messages if msg["role"] == "system"), None)
                user_messages = [msg for msg in messages if msg["role"] == "user"]
                
                # For simplicity, we'll just use the last user message
                user_message = user_messages[-1]["content"] if user_messages else ""
                
                logger.info(f"Sending request to Anthropic API using model {self.model}")
                logger.info(f"System prompt: {system_message[:100]}...")
                logger.info(f"User message: {user_message[:100]}...")
                
                try:
                    response = self.client.messages.create(
                        model=self.model,
                        system=system_message,
                        messages=[{"role": "user", "content": user_message}],
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    logger.info(f"Received response from Anthropic API")
                    return response.content[0].text
                except Exception as e:
                    logger.error(f"Error in Anthropic API call: {e}")
                    logger.error(f"API Key (first 10 chars): {self.api_key[:10]}...")
                    return f"Error in Anthropic API call: {e}"
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return f"Error generating response: {e}"
            
    def rag_query(self, query: str, context: str, temperature: float = 0.2) -> str:
        """
        Process a RAG query and generate a response
        
        Args:
            query (str): User query
            context (str): Retrieved context
            temperature (float): Temperature parameter for generation
            
        Returns:
            str: Generated response
        """
        from .rag_prompt import RAGPromptTemplate
        
        # Format messages for the LLM
        messages = RAGPromptTemplate.format_messages(query, context)
        
        # Generate response
        return self.generate_response(messages, temperature=temperature) 