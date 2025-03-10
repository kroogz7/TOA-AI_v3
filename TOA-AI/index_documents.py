"""
TOA-AI Document Indexing Script
Indexes processed chunks for retrieval
"""

import argparse
import time
from pathlib import Path

# Add the project directory to the path
import sys
sys.path.append(str(Path(__file__).parent))

# Import project components
from config.config import PROCESSED_DIR
from src.processors.vector_indexer import VectorIndexer
from src.utils.logger import get_logger, timer

# Initialize logger
logger = get_logger("IndexDocuments")

@timer
def index_chunks(chunks_path=None, reset=False):
    """
    Index document chunks
    
    Args:
        chunks_path (str, optional): Path to chunks file
        reset (bool): Whether to reset the index
        
    Returns:
        bool: True if indexing was successful
    """
    # Initialize vector indexer
    indexer = VectorIndexer()
    
    # Reset index if requested
    if reset:
        logger.info("Resetting index")
        indexer.reset_index()
    
    # Index chunks
    success = indexer.index_chunks(chunks_path=chunks_path)
    
    return success

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="Index document chunks for retrieval")
    parser.add_argument("--chunks", type=str, default=None, 
                        help="Path to chunks file (defaults to all_chunks.json)")
    parser.add_argument("--reset", action="store_true", default=False,
                        help="Reset the index before indexing")
    
    args = parser.parse_args()
    
    # Use default path if not specified
    chunks_path = args.chunks
    if not chunks_path:
        chunks_path = PROCESSED_DIR / "all_chunks.json"
    
    start_time = time.time()
    
    # Index chunks
    success = index_chunks(chunks_path, args.reset)
    
    end_time = time.time()
    if success:
        logger.info(f"Indexing completed successfully in {end_time - start_time:.2f} seconds")
    else:
        logger.error(f"Indexing failed after {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    main() 