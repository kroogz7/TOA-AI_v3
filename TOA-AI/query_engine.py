#!/usr/bin/env python3
import argparse
import logging
import json
import sys
from src.retrieval import Retriever

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Query the TOA-AI knowledge base")
    parser.add_argument("--vector-store", default="TOA-AI/vector_store", 
                        help="Path to the vector store directory")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", 
                        help="Sentence transformer model name")
    parser.add_argument("--top-k", type=int, default=3, 
                        help="Number of results to return")
    parser.add_argument("--alpha", type=float, default=0.5, 
                        help="Weight for semantic search (1-alpha for lexical)")
    parser.add_argument("--format-output", action="store_true", 
                        help="Format the output as a context string for LLM")
    parser.add_argument("--document", 
                        help="Filter by document ID (e.g., TO 00-25-172CL-1)")
    parser.add_argument("--type", choices=["table", "warning"], 
                        help="Filter by asset type")
    parser.add_argument("--query", 
                        help="Query to search for (if not provided, will run in interactive mode)")
    parser.add_argument("--json", action="store_true", 
                        help="Output results as JSON")
    
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
        print("\n=== TOA-AI Query Engine ===")
        print(f"Loaded vector store with {len(retriever.vector_store.chunks)} chunks")
        print("Type 'exit' to quit\n")
        
        while True:
            query = input("Query: ")
            if query.lower() in ["exit", "quit", "q"]:
                break
            
            process_query(retriever, query, args.top_k, args.alpha, 
                          args.format_output, filter_by, args.json)
    else:
        # Process the provided query
        process_query(retriever, args.query, args.top_k, args.alpha, 
                      args.format_output, filter_by, args.json)

def process_query(retriever, query, top_k, alpha, format_output, filter_by, output_json):
    """Process a query and display results"""
    results = retriever.retrieve(query, k=top_k, alpha=alpha, filter_by=filter_by)
    
    if output_json:
        # Output as JSON
        print(json.dumps(results, indent=2))
        return
    
    if not results:
        print("No results found.")
        return
    
    if format_output:
        # Format for LLM
        context = retriever.format_retrieved_context(results)
        print("\n=== Formatted Context for LLM ===")
        print(context)
    else:
        # Display human-readable results
        print(f"\nFound {len(results)} results:")
        for i, result in enumerate(results):
            metadata = result['metadata']
            print(f"\nResult {i+1} (score: {result['score']:.4f}):")
            print(f"Document: {metadata['document_id']}")
            print(f"Type: {metadata.get('asset_type', 'unknown')}")
            if 'page_num' in metadata:
                print(f"Page: {metadata['page_num'] + 1}")  # Convert to 1-indexed for display
            
            # Truncate content for display if it's too long
            content = result['content']
            if len(content) > 300:
                content = content[:300] + "..."
            print(f"Content: {content}")

if __name__ == "__main__":
    main() 