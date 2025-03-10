"""
TOA-AI Chatbot CLI
Command-line interface for the TOA chatbot
"""

import os
import sys
import argparse
from pathlib import Path
import textwrap

# Add the project directory to the path
sys.path.append(str(Path(__file__).parent))

# Import project components
from src.chatbot.toa_chatbot import TOAChatbot
from src.utils.logger import get_logger

# Initialize logger
logger = get_logger("ChatbotCLI")

def format_answer(response):
    """Format the answer for display"""
    answer = response["answer"]
    sources = response["sources"]
    
    # Format answer with word wrap
    formatted_answer = "\n".join(textwrap.wrap(answer, width=80))
    
    # Add sources
    if sources:
        formatted_answer += "\n\nSources:"
        for source in sources:
            formatted_answer += f"\n- TO {source['to_number']}, Section {source['section_id']} "
            if source['section_title']:
                formatted_answer += f"({source['section_title']})"
            if source['page']:
                formatted_answer += f", Page {source['page']}"
    
    return formatted_answer

def interactive_mode(chatbot):
    """Run the chatbot in interactive mode"""
    print("\n╔═════════════════════════════════════════════════════════════════╗")
    print("║                       TOA-AI Chatbot                            ║")
    print("║     Technical Order Assistant for Aviation Maintenance          ║")
    print("╚═════════════════════════════════════════════════════════════════╝")
    print("\nWelcome to the TOA-AI Chatbot! Ask me anything about your Technical Orders.")
    print("Type 'exit', 'quit', or Ctrl+C to end the session.\n")
    
    while True:
        try:
            # Get user input
            query = input("\n>> ")
            
            # Check if user wants to exit
            if query.lower() in ["exit", "quit", "bye", "goodbye"]:
                print("\nThank you for using TOA-AI. Goodbye!")
                break
                
            # Process query
            print("\nProcessing your query...\n")
            response = chatbot.answer_query(query)
            
            # Display response
            print("\n" + format_answer(response) + "\n")
            
        except KeyboardInterrupt:
            print("\n\nThank you for using TOA-AI. Goodbye!")
            break
        except Exception as e:
            logger.error(f"Error in interactive mode: {str(e)}")
            print(f"\nI encountered an error: {str(e)}")

def single_query_mode(chatbot, query):
    """Run the chatbot for a single query"""
    try:
        # Process query
        print(f"Query: {query}\n")
        print("Processing your query...\n")
        
        response = chatbot.answer_query(query)
        
        # Display response
        print("\n" + format_answer(response) + "\n")
        
    except Exception as e:
        logger.error(f"Error in single query mode: {str(e)}")
        print(f"\nI encountered an error: {str(e)}")

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="TOA-AI Chatbot CLI")
    parser.add_argument("--query", type=str, default=None, 
                        help="Single query mode (default: interactive mode)")
    parser.add_argument("--api-key", type=str, default=None,
                        help="OpenAI API key (default: from environment variable)")
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Warning: No OpenAI API key provided. Set OPENAI_API_KEY environment variable or use --api-key.")
    
    # Initialize chatbot
    try:
        chatbot = TOAChatbot(api_key=api_key)
    except Exception as e:
        logger.error(f"Error initializing chatbot: {str(e)}")
        print(f"Error initializing chatbot: {str(e)}")
        return
    
    # Run in appropriate mode
    if args.query:
        single_query_mode(chatbot, args.query)
    else:
        interactive_mode(chatbot)

if __name__ == "__main__":
    main() 