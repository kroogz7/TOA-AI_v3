import os
import argparse
import logging
from src.retrieval.vector_store import VectorStore

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Build vector store from embeddings")
    parser.add_argument("--embeddings", default="TOA-AI/embeddings/embeddings.json", 
                        help="Path to embeddings file")
    parser.add_argument("--output", default="TOA-AI/vector_store", 
                        help="Output directory for vector store")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", 
                        help="Sentence transformer model name")
    parser.add_argument("--test", action="store_true", 
                        help="Test vector store with sample queries")
    
    args = parser.parse_args()
    
    # Create vector store
    logger.info(f"Creating vector store from {args.embeddings}")
    vector_store = VectorStore(args.embeddings, model_name=args.model)
    
    # Save vector store
    if vector_store.save(args.output):
        logger.info(f"Vector store saved to {args.output}")
    else:
        logger.error("Failed to save vector store")
        return
    
    # Test vector store if requested
    if args.test:
        test_queries = [
            "What are the emergency shutdown procedures for aircraft refueling?",
            "How should I handle fuel servicing in hardened aircraft shelters?",
            "What are the safety precautions for concurrent servicing operations?",
            "What is hot refueling and when should it be used?",
            "What warnings are there about commercial fuel servicing trucks?"
        ]
        
        logger.info("Testing vector store with sample queries")
        for query in test_queries:
            logger.info(f"Query: {query}")
            results = vector_store.search(query, k=3)
            
            logger.info(f"Found {len(results)} results")
            for i, (chunk, score) in enumerate(results):
                logger.info(f"Result {i+1} (score: {score:.4f}):")
                logger.info(f"Document: {chunk['metadata']['document_id']}")
                logger.info(f"Type: {chunk['type']}")
                if 'page_num' in chunk['metadata']:
                    logger.info(f"Page: {chunk['metadata']['page_num'] + 1}")
                logger.info(f"Content snippet: {chunk['content'][:100]}...")
                logger.info("-" * 40)
    
    logger.info("Done")

if __name__ == "__main__":
    main() 