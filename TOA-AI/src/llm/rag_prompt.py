class RAGPromptTemplate:
    """
    A template for formatting RAG prompts to be sent to LLMs
    """
    
    @staticmethod
    def get_system_prompt():
        """Get the system prompt for the LLM"""
        return """You are TOA-AI, an intelligent assistant for maintenance personnel who work with Technical Orders (TOs). 
You have access to a database of TO documents that contain important aircraft maintenance and servicing information.
Your goal is to provide accurate, concise, and helpful information based on the technical documents.

When responding:
1. Base your answers ONLY on the provided context information. Do not use prior knowledge.
2. If the context doesn't contain the answer, say "I don't have enough information to answer this question based on the available documents."
3. Always cite your sources using the format [Document ID, Page Number, Content Type].
4. Be concise and focused on answering the user's question directly.
5. For warnings, cautions, or notes, ensure they are prominently highlighted in your response.
6. Use bullet points or numbered lists when appropriate to improve readability.
7. Maintain a professional and authoritative tone appropriate for technical documentation.
"""

    @staticmethod
    def format_prompt(query, context):
        """
        Format a prompt for the RAG application
        
        Args:
            query (str): The user's query
            context (str): The retrieved context information
            
        Returns:
            dict: The formatted prompt message dictionary for an LLM
        """
        user_prompt = f"""Please answer the following question based on the provided document context.

Question: {query}

Context Information:
{context}

Answer:"""

        return user_prompt
    
    @staticmethod
    def format_messages(query, context):
        """
        Format the messages for a chat-based LLM API
        
        Args:
            query (str): The user's query
            context (str): The retrieved context information
            
        Returns:
            list: A list of message dictionaries for a chat API
        """
        return [
            {"role": "system", "content": RAGPromptTemplate.get_system_prompt()},
            {"role": "user", "content": RAGPromptTemplate.format_prompt(query, context)}
        ] 