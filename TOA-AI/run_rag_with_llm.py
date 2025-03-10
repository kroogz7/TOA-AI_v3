#!/usr/bin/env python3
import argparse
import logging
import sys
import os
from dotenv import load_dotenv
from src.retrieval import Retriever
from src.llm import LLMConnector, LLMProvider

# Load environment variables from .env file if it exists
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="TOA-AI RAG with LLM Integration")
    parser.add_argument("--vector-store", default="TOA-AI/vector_store", 
                        help="Path to the vector store directory")
    parser.add_argument("--model", default=None, 
                        help="LLM model name (defaults to environment variable or provider default)")
    parser.add_argument("--provider", default=None, choices=["openai", "anthropic"],
                        help="LLM provider (openai or anthropic, defaults to environment variable or openai)")
    parser.add_argument("--top-k", type=int, default=5, 
                        help="Number of results to return")
    parser.add_argument("--alpha", type=float, default=0.5, 
                        help="Weight for semantic search (1-alpha for lexical)")
    parser.add_argument("--temperature", type=float, default=0.2,
                        help="Temperature for LLM generation (0.0-1.0)")
    parser.add_argument("--document", 
                        help="Filter by document ID (e.g., TO 00-25-172CL-1)")
    parser.add_argument("--type", choices=["table", "warning"], 
                        help="Filter by asset type")
    parser.add_argument("--query", 
                        help="Query to search for (if not provided, will run in interactive mode)")
    parser.add_argument("--openai-key", 
                        help="OpenAI API key (overrides environment variable)")
    parser.add_argument("--anthropic-key", 
                        help="Anthropic API key (overrides environment variable)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with more detailed output")
    
    args = parser.parse_args()
    
    # Set logging level based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Set API keys from arguments if provided
    if args.openai_key:
        os.environ["OPENAI_API_KEY"] = args.openai_key
    if args.anthropic_key:
        os.environ["ANTHROPIC_API_KEY"] = args.anthropic_key
    
    # Create LLM connector
    llm = LLMConnector(provider=args.provider, model=args.model)
    
    # Print information about the LLM being used
    logger.info(f"Using {llm.provider} with model {llm.model}")
    
    # Create and load retriever
    retriever = Retriever(args.vector_store)
    if not retriever.vector_store:
        logger.error(f"Failed to load vector store from {args.vector_store}")
        sys.exit(1)
    
    logger.info(f"Loaded vector store with {len(retriever.vector_store.chunks)} chunks")
    
    # Prepare filter if any
    filter_by = {}
    if args.document:
        filter_by["document_id"] = args.document
    if args.type:
        filter_by["asset_type"] = args.type
    
    # If no query provided, run in interactive mode
    if not args.query:
        print("\n=== TOA-AI RAG with LLM Integration ===")
        print(f"Using {llm.provider} with model {llm.model}")
        print(f"Loaded vector store with {len(retriever.vector_store.chunks)} chunks")
        print("Type 'exit' to quit\n")
        
        while True:
            query = input("Query: ")
            if query.lower() in ["exit", "quit", "q"]:
                break
            
            process_query(retriever, llm, query, args.top_k, args.alpha, args.temperature, filter_by)
    else:
        # Process the provided query
        process_query(retriever, llm, args.query, args.top_k, args.alpha, args.temperature, filter_by)

def process_query(retriever, llm, query, top_k, alpha, temperature, filter_by):
    """Process a query and generate a response using the LLM"""
    print(f"\nProcessing query: {query}")
    
    try:
        # Retrieve relevant chunks
        results = retriever.retrieve(query, k=top_k, alpha=alpha, filter_by=filter_by)
        
        if not results:
            print("No results found.")
            return
        
        print(f"Found {len(results)} relevant chunks")
        
        # Format context for LLM
        context = retriever.format_retrieved_context(results)
        
        # Generate response with the LLM
        print("\nGenerating response...")
        response = llm.rag_query(query, context, temperature=temperature)
        
        # Print response
        print("\n=== Response ===")
        print(response)
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 