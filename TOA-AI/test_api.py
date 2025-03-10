#!/usr/bin/env python3
import requests
import json
import argparse

def main():
    parser = argparse.ArgumentParser(description="Test the TOA-AI API")
    parser.add_argument("--url", default="http://localhost:8000", help="API URL")
    parser.add_argument("--query", default="What are the safety precautions for hot refueling operations?", 
                        help="Query to search for")
    parser.add_argument("--top-k", type=int, default=3, help="Number of results to return")
    parser.add_argument("--document", help="Filter by document ID")
    parser.add_argument("--type", help="Filter by asset type (e.g., table, warning)")
    parser.add_argument("--list-documents", action="store_true", help="List available documents")
    parser.add_argument("--list-asset-types", action="store_true", help="List available asset types")
    parser.add_argument("--list-providers", action="store_true", help="List available LLM providers")
    parser.add_argument("--generate", action="store_true", help="Generate response using LLM")
    parser.add_argument("--provider", default="openai", help="LLM provider (openai or anthropic)")
    parser.add_argument("--model", help="LLM model name (defaults to provider default)")
    parser.add_argument("--temperature", type=float, default=0.2, help="Temperature for LLM (0.0-1.0)")
    
    args = parser.parse_args()
    
    # Check if API is running
    try:
        response = requests.get(f"{args.url}/")
        if response.status_code == 200:
            print(f"API is running: {response.json()}")
        else:
            print(f"API returned status code {response.status_code}")
            return
    except Exception as e:
        print(f"Error connecting to API: {e}")
        return
    
    # List documents if requested
    if args.list_documents:
        try:
            response = requests.get(f"{args.url}/documents")
            if response.status_code == 200:
                documents = response.json().get("documents", [])
                print("\nAvailable documents:")
                for doc in documents:
                    print(f"- {doc}")
            else:
                print(f"Failed to get documents: {response.status_code}")
        except Exception as e:
            print(f"Error getting documents: {e}")
    
    # List asset types if requested
    if args.list_asset_types:
        try:
            response = requests.get(f"{args.url}/asset_types")
            if response.status_code == 200:
                asset_types = response.json().get("asset_types", [])
                print("\nAvailable asset types:")
                for asset_type in asset_types:
                    print(f"- {asset_type}")
            else:
                print(f"Failed to get asset types: {response.status_code}")
        except Exception as e:
            print(f"Error getting asset types: {e}")
    
    # List LLM providers if requested
    if args.list_providers:
        try:
            response = requests.get(f"{args.url}/llm_providers")
            if response.status_code == 200:
                providers = response.json().get("providers", [])
                print("\nAvailable LLM providers:")
                for provider in providers:
                    print(f"- {provider}")
            else:
                print(f"Failed to get providers: {response.status_code}")
        except Exception as e:
            print(f"Error getting providers: {e}")
    
    # If no query provided and only listing was requested, exit
    if not args.query and (args.list_documents or args.list_asset_types or args.list_providers):
        return
    
    # Determine if we're using the generate endpoint or just querying
    if args.generate:
        # Prepare request for LLM generation
        query_data = {
            "query": args.query,
            "top_k": args.top_k,
            "provider": args.provider,
            "temperature": args.temperature
        }
        
        if args.model:
            query_data["model"] = args.model
        
        if args.document:
            query_data["document_id"] = args.document
        
        if args.type:
            query_data["asset_type"] = args.type
        
        # Send generation request
        try:
            print(f"\nSending query to generate response: {args.query}")
            print(f"Using provider: {args.provider}")
            
            response = requests.post(f"{args.url}/generate", json=query_data)
            
            if response.status_code == 200:
                result = response.json()
                
                # Print results
                print(f"\nFound {len(result['results'])} results and generated a response:")
                
                # Print LLM response
                print("\n=== LLM Response ===")
                print(result['response'])
                
                # Print source chunks
                print("\n=== Source Information ===")
                for i, chunk in enumerate(result['results']):
                    metadata = chunk['metadata']
                    print(f"\n--- Source {i+1} (Score: {chunk['score']:.4f}) ---")
                    print(f"Document: {metadata['document_id']}, Page: {metadata['page_num'] + 1}, Type: {metadata['asset_type']}")
            else:
                print(f"Generation failed with status code {response.status_code}")
                print(response.text)
        
        except Exception as e:
            print(f"Error generating response: {e}")
    
    else:
        # Regular query without LLM generation
        # Prepare query request
        query_data = {
            "query": args.query,
            "top_k": args.top_k,
            "format_for_llm": True
        }
        
        if args.document:
            query_data["document_id"] = args.document
        
        if args.type:
            query_data["asset_type"] = args.type
        
        # Send query request
        try:
            print(f"\nSending query: {args.query}")
            response = requests.post(f"{args.url}/query", json=query_data)
            
            if response.status_code == 200:
                result = response.json()
                
                # Print results
                print(f"\nFound {len(result['results'])} results:")
                for i, chunk in enumerate(result['results']):
                    metadata = chunk['metadata']
                    print(f"\n--- Result {i+1} (Score: {chunk['score']:.4f}) ---")
                    print(f"Document: {metadata['document_id']}, Page: {metadata['page_num'] + 1}, Type: {metadata['asset_type']}")
                    print(f"Content: {chunk['content'][:200]}...")
                
                # Print formatted context
                if result.get('context'):
                    print("\n=== Formatted Context for LLM ===")
                    print(result['context'])
                
                # Print messages for LLM
                if result.get('messages'):
                    print("\n=== Messages for LLM API ===")
                    print(json.dumps(result['messages'], indent=2))
            else:
                print(f"Query failed with status code {response.status_code}")
                print(response.text)
        
        except Exception as e:
            print(f"Error querying API: {e}")

if __name__ == "__main__":
    main() 