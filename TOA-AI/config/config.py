"""
TOA-AI Configuration File
Contains all project paths and configuration settings
"""

import os
from pathlib import Path

# Project root paths
ROOT_DIR = Path(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))
DATA_DIR = ROOT_DIR.parent / "DATA"  # Original PDF files
PROCESSED_DIR = ROOT_DIR / "processed"  # Processed data
ASSETS_DIR = ROOT_DIR / "assets"  # Extracted images and tables
INDEX_DIR = ROOT_DIR / "index"  # Vector indices
CONFIG_DIR = ROOT_DIR / "config"  # Configuration files

# Assets subdirectories
IMAGE_DIR = ASSETS_DIR / "images"
TABLE_DIR = ASSETS_DIR / "tables"
TEXT_DIR = ASSETS_DIR / "text"
WARNING_DIR = ASSETS_DIR / "warnings"

# Ensure all directories exist
for dir_path in [DATA_DIR, PROCESSED_DIR, ASSETS_DIR, INDEX_DIR, CONFIG_DIR,
                IMAGE_DIR, TABLE_DIR, TEXT_DIR, WARNING_DIR]:
    os.makedirs(dir_path, exist_ok=True)

# PDF Processing settings
PDF_PROCESSING = {
    "dpi": 300,  # DPI for converting PDF to images
    "ocr_lang": "eng",  # Language for OCR
    "min_text_length": 10,  # Minimum text length to consider valid
    "table_extraction_mode": "lattice",  # Default table extraction mode (lattice or stream)
    "image_formats": ["png", "jpg", "jpeg"],  # Supported image formats
    "tesseract_path": r"C:\Program Files\Tesseract-OCR\tesseract.exe",  # Path to Tesseract executable (Windows)
}

# Document structure settings
DOCUMENT_STRUCTURE = {
    "section_patterns": [
        r"^(\d+\.\d+(?:\.\d+)*)\s+([A-Z].*?)$",  # Regular section numbers (e.g., "1.2.3 SECTION TITLE")
        r"^(CHAPTER|SECTION)\s+(\d+(?:\.\d+)*)\s+([A-Z].*?)$"  # Chapter/Section format
    ],
    "warning_patterns": [
        r"(?i)(?:^|\n)(WARNING|CAUTION|NOTE):\s*(.*?)(?=\n\n|\n[A-Z]|\n\d+\.|\Z)",
        r"(?i)(WARNING|CAUTION|NOTE)(?:\s+BOX)?\s*:?\s*(.*?)(?=\n\n|\n[A-Z])"
    ],
    "figure_patterns": [
        r"(?i)(?:Figure|Fig\.)\s+(\d+(?:-\d+)?)(?:\.|\:)?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)",
        r"(?i)(?:FIGURE|FIG)\s+(\d+(?:-\d+)?)(?:\.|\:)?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)"
    ],
    "table_patterns": [
        r"(?i)(?:Table|Tab\.)\s+(\d+(?:-\d+)?)(?:\.|\:)?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)",
        r"(?i)(?:TABLE|TAB)\s+(\d+(?:-\d+)?)(?:\.|\:)?\s*(.*?)(?=\n\n|\n[A-Z]|\Z)"
    ],
    "afto_form_pattern": r"(?i)AFTO\s+FORM\s+(\d+)",
    "to_number_pattern": r"(?i)TO\s+(\d+(?:-\d+){2,}(?:\w+)?(?:-\d+)?)"
}

# Chunking settings
CHUNKING = {
    "chunk_size": 512,  # Target chunk size in characters
    "chunk_overlap": 50,  # Overlap between chunks in characters
    "special_break_chars": [".", "!", "?", "\n\n"],  # Characters to break chunks on
    "preserve_warnings": True,  # Keep warnings as separate chunks
    "preserve_procedures": True,  # Keep procedures as separate chunks
    "preserve_tables": True,  # Keep tables as separate chunks
}

# Vector database settings
VECTOR_DB = {
    "embedding_model": "all-mpnet-base-v2",  # Sentence transformer model
    "image_embedding_model": "clip-ViT-B-32",  # Image embedding model
    "collection_name": "toa_maintenance_docs",  # ChromaDB collection name
    "distance_metric": "cosine",  # Distance metric for vector search
    "top_k": 5,  # Default number of results to return
}

# LLM settings
LLM = {
    "model": "gpt-3.5-turbo",  # Default OpenAI model
    "temperature": 0.0,  # Response temperature (0 = deterministic)
    "max_tokens": 1024,  # Maximum response length
    "system_prompt": """You are TOA-AI, a specialized assistant for aviation maintenance based on Technical Orders (TOs).
Always provide accurate information from the TOs.
Present safety information first, including WARNINGS and CAUTIONS.
Cite specific document sections (e.g., "According to TO 00-25-172CL-1, Section 3.4").
Use markdown formatting to improve readability.
If not confident in an answer, acknowledge limitations.
"""
}

# Logging settings
LOGGING = {
    "log_level": "INFO",
    "log_to_file": True,
    "log_file": ROOT_DIR / "logs" / "toa_ai.log",
}

# Create logs directory
os.makedirs(ROOT_DIR / "logs", exist_ok=True) 