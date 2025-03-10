"""
TOA-AI Run Script
Provides a simple interface to run the full TOA-AI pipeline
"""

import os
import sys
import argparse
import time
from pathlib import Path

# Add parent directory to system path
sys.path.append(str(Path(__file__).parent))

# Import project components
from config.config import DATA_DIR
from process_pdfs import process_directory, process_pdf
from index_documents import index_chunks
from src.chatbot.toa_chatbot import TOAChatbot
from src.utils.logger import get_logger

# Initialize logger
logger = get_logger("RunScript")

def run_full_pipeline(pdf_dir=None, single_pdf=None, reset_index=True):
    """
    Run the full TOA-AI pipeline: process PDFs, index documents, start chatbot
    
    Args:
        pdf_dir (str, optional): Directory containing PDF files
        single_pdf (str, optional): Path to a single PDF file
        reset_index (bool): Whether to reset the index
        
    Returns:
        TOAChatbot: Initialized chatbot instance
    """
    start_time = time.time()
    
    # Step 1: Process PDFs
    logger.info("Step 1: Processing PDFs")
    if single_pdf:
        _, chunks = process_pdf(single_pdf)
    else:
        _, chunks = process_directory(pdf_dir or DATA_DIR)
    
    # Step 2: Index Documents
    logger.info("Step 2: Indexing Documents")
    index_chunks(reset=reset_index)
    
    # Step 3: Initialize Chatbot
    logger.info("Step 3: Initializing Chatbot")
    chatbot = TOAChatbot()
    
    end_time = time.time()
    logger.info(f"Pipeline completed in {end_time - start_time:.2f} seconds")
    
    return chatbot

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Run the TOA-AI pipeline")
    parser.add_argument("--dir", type=str, default=None, 
                        help="Directory containing PDF files")
    parser.add_argument("--single", type=str, default=None,
                        help="Process a single PDF file")
    parser.add_argument("--skip-processing", action="store_true", default=False,
                        help="Skip PDF processing (use existing processed files)")
    parser.add_argument("--skip-indexing", action="store_true", default=False,
                        help="Skip document indexing (use existing index)")
    parser.add_argument("--chat", action="store_true", default=False,
                        help="Start interactive chat session after processing")
    parser.add_argument("--query", type=str, default=None,
                        help="Run a single query after processing")
    
    args = parser.parse_args()
    
    start_time = time.time()
    
    # Initialize chatbot
    chatbot = None
    
    # Full pipeline if not skipping steps
    if not args.skip_processing and not args.skip_indexing:
        chatbot = run_full_pipeline(args.dir, args.single)
    else:
        # Step 1: Process PDFs (if not skipped)
        if not args.skip_processing:
            logger.info("Processing PDFs")
            if args.single:
                process_pdf(args.single)
            else:
                process_directory(args.dir or DATA_DIR)
        
        # Step 2: Index Documents (if not skipped)
        if not args.skip_indexing:
            logger.info("Indexing Documents")
            index_chunks(reset=True)
        
        # Step 3: Initialize Chatbot
        logger.info("Initializing Chatbot")
        chatbot = TOAChatbot()
    
    # Run chat or query if requested
    if args.chat and chatbot:
        from chatbot_cli import interactive_mode
        interactive_mode(chatbot)
    elif args.query and chatbot:
        from chatbot_cli import single_query_mode
        single_query_mode(chatbot, args.query)
    
    end_time = time.time()
    logger.info(f"Total runtime: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main() 