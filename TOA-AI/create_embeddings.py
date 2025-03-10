import json
import os
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
import logging
import torch
import argparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def load_chunks(chunks_path):
    """Load chunks from a JSON file"""
    logger.info(f"Loading chunks from {chunks_path}")
    try:
        with open(chunks_path, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        logger.info(f"Loaded {len(chunks)} chunks")
        return chunks
    except Exception as e:
        logger.error(f"Error loading chunks: {e}")
        return []

def create_embeddings(chunks, model_name="all-MiniLM-L6-v2", batch_size=32):
    """Create embeddings for the chunks using the specified model"""
    logger.info(f"Creating embeddings using {model_name}")
    
    # Get device (use GPU if available)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    
    # Load the model
    model = SentenceTransformer(model_name, device=device)
    
    # Extract text from chunks
    texts = [chunk["content"] for chunk in chunks]
    
    # Generate embeddings
    logger.info(f"Generating embeddings for {len(texts)} chunks")
    embeddings = []
    
    # Process in batches
    for i in tqdm(range(0, len(texts), batch_size)):
        batch_texts = texts[i:i+batch_size]
        batch_embeddings = model.encode(batch_texts, show_progress_bar=False)
        embeddings.extend(batch_embeddings)
    
    # Convert to a numpy array
    embeddings = np.array(embeddings)
    logger.info(f"Generated embeddings with shape: {embeddings.shape}")
    
    return embeddings

def save_embeddings(embeddings, chunks, output_path):
    """Save embeddings and their corresponding chunks"""
    logger.info(f"Saving embeddings to {output_path}")
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Prepare data for saving
    data = {
        "embeddings": embeddings.tolist(),
        "chunks": chunks
    }
    
    # Save to file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    
    logger.info(f"Embeddings saved successfully")

def main():
    parser = argparse.ArgumentParser(description="Generate embeddings for document chunks")
    parser.add_argument("--chunks", default="TOA-AI/processed/all_chunks.json", help="Path to chunks file")
    parser.add_argument("--output", default="TOA-AI/embeddings/embeddings.json", help="Output path for embeddings")
    parser.add_argument("--model", default="all-MiniLM-L6-v2", help="Sentence transformer model to use")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for embedding generation")
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    
    # Load chunks
    chunks = load_chunks(args.chunks)
    
    if not chunks:
        logger.error("No chunks loaded. Exiting.")
        return
    
    # Create embeddings
    embeddings = create_embeddings(chunks, model_name=args.model, batch_size=args.batch_size)
    
    # Save embeddings
    save_embeddings(embeddings, chunks, args.output)
    
    logger.info("Embedding generation complete")

if __name__ == "__main__":
    main() 