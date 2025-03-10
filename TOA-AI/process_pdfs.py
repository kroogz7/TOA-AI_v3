"""
TOA-AI PDF Processing Script
Processes Technical Order PDFs for RAG
"""

import argparse
import os
import json
import time
from pathlib import Path
from tqdm import tqdm

# Add the project directory to the path
import sys
sys.path.append(str(Path(__file__).parent))

# Import project components
from config.config import DATA_DIR, PROCESSED_DIR
from src.processors.pdf_processor import PDFProcessor
from src.processors.document_chunker import DocumentChunker
from src.utils.logger import get_logger, timer

# Initialize logger
logger = get_logger("ProcessPDFs")

@timer
def process_pdf(pdf_path):
    """
    Process a single PDF file
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        dict: Processed document
    """
    logger.info(f"Processing PDF: {pdf_path}")
    
    # Initialize PDF processor
    processor = PDFProcessor(pdf_path)
    
    # Process document
    document = processor.process_document()
    
    # Save processed document
    output_path = PROCESSED_DIR / f"{document['id']}_processed.json"
    with open(output_path, "w") as f:
        json.dump(document, f, indent=2)
    
    logger.info(f"Saved processed document to {output_path}")
    
    # Create and save chunks
    chunker = DocumentChunker(document)
    chunks = chunker.create_chunks()
    chunks_path = chunker.save_chunks()
    
    logger.info(f"Processing complete for {pdf_path}")
    
    return document, chunks

@timer
def process_directory(dir_path=DATA_DIR, file_pattern="*.pdf"):
    """
    Process all PDF files in a directory
    
    Args:
        dir_path (str): Directory containing PDF files
        file_pattern (str): Pattern to match PDF files
        
    Returns:
        list: List of processed documents
        list: List of all chunks
    """
    # Get all PDF files in the directory
    pdf_files = list(Path(dir_path).glob(file_pattern))
    
    if not pdf_files:
        logger.warning(f"No PDF files found in {dir_path} matching pattern {file_pattern}")
        return [], []
    
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    # Process each PDF file
    processed_docs = []
    all_chunks = []
    
    for pdf_file in tqdm(pdf_files, desc="Processing PDFs"):
        try:
            document, chunks = process_pdf(pdf_file)
            processed_docs.append(document)
            all_chunks.extend(chunks)
        except Exception as e:
            logger.error(f"Error processing {pdf_file}: {str(e)}")
    
    # Save all chunks to a single file for easier indexing
    all_chunks_path = PROCESSED_DIR / "all_chunks.json"
    with open(all_chunks_path, "w") as f:
        json.dump(all_chunks, f, indent=2)
    
    logger.info(f"Processed {len(processed_docs)} documents with {len(all_chunks)} total chunks")
    logger.info(f"All chunks saved to {all_chunks_path}")
    
    return processed_docs, all_chunks

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Process Technical Order PDFs for RAG")
    parser.add_argument("--dir", type=str, default=str(DATA_DIR), 
                        help="Directory containing PDF files")
    parser.add_argument("--pattern", type=str, default="*.pdf", 
                        help="Pattern to match PDF files")
    parser.add_argument("--single", type=str, default=None,
                        help="Process a single PDF file")
    
    args = parser.parse_args()
    
    start_time = time.time()
    
    if args.single:
        # Process a single PDF file
        process_pdf(args.single)
    else:
        # Process all PDFs in the directory
        process_directory(args.dir, args.pattern)
    
    end_time = time.time()
    logger.info(f"Total processing time: {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main() 