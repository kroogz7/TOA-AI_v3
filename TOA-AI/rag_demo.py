#!/usr/bin/env python3
import argparse
import logging
import sys
from src.retrieval import Retriever
from src.llm import RAGPromptTemplate

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="TOA-AI RAG Demo")
    parser.add_argument("--vector-store", default="TOA-AI/vector_store", 
                        help="Path to the vector store directory")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", 
                        help="Sentence transformer model name")
    parser.add_argument("--top-k", type=int, default=5, 
                        help="Number of results to return")
    parser.add_argument("--alpha", type=float, default=0.5, 
                        help="Weight for semantic search (1-alpha for lexical)")
    parser.add_argument("--document", 
                        help="Filter by document ID (e.g., TO 00-25-172CL-1)")
    parser.add_argument("--type", choices=["table", "warning"], 
                        help="Filter by asset type")
    parser.add_argument("--query", 
                        help="Query to search for (if not provided, will run in interactive mode)")
    
    args = parser.parse_args()
    
    # Create and load retriever
    retriever = Retriever(args.vector_store, model_name=args.model)
    if not retriever.vector_store:
        logger.error(f"Failed to load vector store from {args.vector_store}")
        sys.exit(1)
    
    # Prepare filter if any
    filter_by = {}
    if args.document:
        filter_by["document_id"] = args.document
    if args.type:
        filter_by["asset_type"] = args.type
    
    # If no query provided, run in interactive mode
    if not args.query:
        print("\n=== TOA-AI RAG Demo ===")
        print(f"Loaded vector store with {len(retriever.vector_store.chunks)} chunks")
        print("Type 'exit' to quit\n")
        
        while True:
            query = input("Query: ")
            if query.lower() in ["exit", "quit", "q"]:
                break
            
            process_query(retriever, query, args.top_k, args.alpha, filter_by)
    else:
        # Process the provided query
        process_query(retriever, args.query, args.top_k, args.alpha, filter_by)

def process_query(retriever, query, top_k, alpha, filter_by):
    """Process a query and display results"""
    print(f"\nProcessing query: {query}")
    
    # Retrieve relevant chunks
    results = retriever.retrieve(query, k=top_k, alpha=alpha, filter_by=filter_by)
    
    if not results:
        print("No results found.")
        return
    
    print(f"Found {len(results)} relevant chunks")
    
    # Format context for LLM
    context = retriever.format_retrieved_context(results)
    
    # Format prompt for LLM
    messages = RAGPromptTemplate.format_messages(query, context)
    
    # In a real implementation, we would send these messages to an LLM API
    # For this demo, we'll just print the prompt
    print("\n=== System Prompt ===")
    print(messages[0]['content'])
    
    print("\n=== User Prompt ===")
    print(messages[1]['content'])
    
    print("\n=== In a real implementation, this prompt would be sent to an LLM API ===")
    print("For example, using OpenAI's API:")
    print("```python")
    print("from openai import OpenAI")
    print("client = OpenAI()")
    print("response = client.chat.completions.create(")
    print("    model='gpt-4',")
    print("    messages=messages,")
    print("    temperature=0.1")
    print(")")
    print("print(response.choices[0].message.content)")
    print("```")

if __name__ == "__main__":
    main() 