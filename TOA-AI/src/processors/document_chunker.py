"""
TOA-AI Document Chunker
Processes extracted document content into optimized chunks for RAG
"""

import re
import json
from pathlib import Path
import sys
import uuid

# Add parent directory to system path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.config import CHUNKING, PROCESSED_DIR
from src.utils.logger import get_logger, timer

logger = get_logger("DocumentChunker")

class DocumentChunker:
    """
    Processes extracted document content into optimized chunks for RAG
    """
    
    def __init__(self, document, chunk_settings=None):
        """
        Initialize the document chunker
        
        Args:
            document (dict): Processed document content
            chunk_settings (dict, optional): Chunk settings to override defaults
        """
        self.document = document
        self.document_id = document["id"]
        self.chunk_settings = chunk_settings or CHUNKING
        
        # Initialize chunk storage
        self.chunks = []
    
    @timer
    def create_chunks(self):
        """
        Create chunks from the document content
        
        Returns:
            list: List of chunks
        """
        # First handle warnings if configured to preserve them
        if self.chunk_settings["preserve_warnings"]:
            self._create_warning_chunks()
        
        # Then handle tables if configured to preserve them
        if self.chunk_settings["preserve_tables"]:
            self._create_table_chunks()
        
        # Process sections into chunks if sections exist
        if self.document["sections"] and len(self.document["sections"]) > 0:
            self._create_section_chunks()
        else:
            # If no sections were found, create chunks from raw document content
            logger.info(f"No sections found in document {self.document_id}, creating chunks from raw content")
            self._create_raw_content_chunks()
        
        logger.info(f"Created {len(self.chunks)} chunks for document {self.document_id}")
        
        return self.chunks
    
    def _create_raw_content_chunks(self):
        """Create chunks from raw content when no sections are available"""
        from src.utils.asset_manager import AssetManager
        asset_manager = AssetManager(self.document_id)
        
        # Load registries
        asset_manager._load_registries()
        
        # Check if registries are populated
        if not asset_manager.table_registry and not asset_manager.warning_registry:
            logger.error(f"Could not load asset registry for document {self.document_id}")
            return
        
        # Create chunks from tables
        if asset_manager.table_registry:
            for table_id, table_info in asset_manager.table_registry.items():
                # Read table content from MD file
                try:
                    with open(table_info["md_path"], "r", encoding="utf-8") as f:
                        table_content = f.read()
                    
                    # Create a chunk for this table
                    chunk_id = f"chunk_{self.document_id}_table_{table_id}"
                    
                    chunk = {
                        "id": chunk_id,
                        "type": "table",
                        "content": f"TABLE FROM DOCUMENT {self.document_id}, PAGE {table_info['page_num']+1}\n\n{table_content}",
                        "metadata": {
                            "document_id": self.document_id,
                            "to_number": self.document["metadata"]["to_number"],
                            "section_id": "unknown",
                            "section_title": "unknown",
                            "page_num": table_info["page_num"],
                            "asset_id": table_id,
                            "asset_type": "table"
                        }
                    }
                    
                    self.chunks.append(chunk)
                    logger.info(f"Created chunk from table {table_id}")
                except Exception as e:
                    logger.error(f"Error creating chunk from table {table_id}: {e}")
        
        # Create chunks from warnings
        if asset_manager.warning_registry:
            for warning_id, warning_info in asset_manager.warning_registry.items():
                try:
                    # Check if the warning info has a file_path or path key
                    file_path = None
                    if "file_path" in warning_info:
                        file_path = warning_info["file_path"]
                    elif "path" in warning_info:
                        file_path = warning_info["path"]
                    else:
                        logger.error(f"Warning {warning_id} does not have a path key")
                        continue
                    
                    with open(file_path, "r", encoding="utf-8") as f:
                        warning_content = f.read()
                    
                    # Create a chunk for this warning
                    chunk_id = f"chunk_{self.document_id}_warning_{warning_id}"
                    
                    # Get warning type, defaulting to "WARNING" if not found
                    warning_type = warning_info.get("type", "WARNING")
                    
                    chunk = {
                        "id": chunk_id,
                        "type": "warning",
                        "content": f"{warning_type} FROM DOCUMENT {self.document_id}, PAGE {warning_info['page_num']+1}\n\n{warning_content}",
                        "metadata": {
                            "document_id": self.document_id,
                            "to_number": self.document["metadata"]["to_number"],
                            "section_id": "unknown",
                            "section_title": "unknown",
                            "page_num": warning_info["page_num"],
                            "asset_id": warning_id,
                            "asset_type": "warning",
                            "warning_type": warning_type
                        }
                    }
                    
                    self.chunks.append(chunk)
                    logger.info(f"Created chunk from warning {warning_id}")
                except Exception as e:
                    logger.error(f"Error creating chunk from warning {warning_id}: {e}")
    
    def _create_warning_chunks(self):
        """Create standalone chunks for warnings"""
        # Find all warnings in the document (from asset registry)
        for section in self.document["sections"]:
            for warning_id in section["assets"]["warnings"]:
                # Create a standalone chunk for each warning
                warning_chunk = {
                    "id": f"chunk_warning_{warning_id}",
                    "type": "warning",
                    "content": f"SECTION {section['id']} {section['title']}\n\n"
                              f"WARNING: {self._get_warning_content(warning_id)}",
                    "metadata": {
                        "document_id": self.document_id,
                        "to_number": self.document["metadata"]["to_number"],
                        "section_id": section["id"],
                        "section_title": section["title"],
                        "page": section["page"],
                        "chunk_type": "warning",
                        "contains_warning": True
                    }
                }
                
                self.chunks.append(warning_chunk)
    
    def _get_warning_content(self, warning_id):
        """Get warning content from document structure"""
        # This is a simplified approach - in production you'd query the AssetManager
        for section in self.document["sections"]:
            for warning in section["assets"].get("warnings", []):
                if warning == warning_id:
                    # Return placeholder if we can't get actual content
                    return "Warning content placeholder"
        return "Warning content not found"
    
    def _create_table_chunks(self):
        """Create standalone chunks for tables"""
        # Find all tables in the document (from asset registry)
        for section in self.document["sections"]:
            for table_id in section["assets"]["tables"]:
                # Create a standalone chunk for each table
                table_chunk = {
                    "id": f"chunk_table_{table_id}",
                    "type": "table",
                    "content": f"SECTION {section['id']} {section['title']}\n\n"
                              f"TABLE: {self._get_table_content(table_id)}",
                    "metadata": {
                        "document_id": self.document_id,
                        "to_number": self.document["metadata"]["to_number"],
                        "section_id": section["id"],
                        "section_title": section["title"],
                        "page": section["page"],
                        "chunk_type": "table",
                        "contains_table": True
                    }
                }
                
                self.chunks.append(table_chunk)
    
    def _get_table_content(self, table_id):
        """Get table content from document structure"""
        # This is a simplified approach - in production you'd query the AssetManager
        for section in self.document["sections"]:
            for table in section["assets"].get("tables", []):
                if table == table_id:
                    # Return placeholder if we can't get actual content
                    return "Table content placeholder"
        return "Table content not found"
    
    def _create_section_chunks(self):
        """Create chunks from document sections"""
        for section in self.document["sections"]:
            # Skip empty sections
            if not section["content"] or len(section["content"].strip()) < 10:
                continue
            
            # Prepare the content with section header
            content = f"SECTION {section['id']} {section['title']}\n\n{section['content']}"
            
            # Check if content fits in a single chunk
            if len(content) <= self.chunk_settings["chunk_size"]:
                self._add_section_chunk(content, section)
            else:
                # Split into multiple chunks
                self._split_section_into_chunks(content, section)
    
    def _add_section_chunk(self, content, section, chunk_index=0):
        """Add a chunk for a section"""
        # Create chunk ID
        chunk_id = f"chunk_{self.document_id}_{section['id'].replace('.', '_')}_{chunk_index}"
        
        # Determine if chunk contains warnings
        contains_warning = bool(re.search(r'WARNING|CAUTION|NOTE', content, re.IGNORECASE))
        
        # Create the chunk
        chunk = {
            "id": chunk_id,
            "type": "section",
            "content": content,
            "metadata": {
                "document_id": self.document_id,
                "to_number": self.document["metadata"]["to_number"],
                "section_id": section["id"],
                "section_title": section["title"],
                "page": section["page"],
                "chunk_type": "section",
                "chunk_index": chunk_index,
                "contains_warning": contains_warning,
                "images": section["assets"]["images"],
                "tables": section["assets"]["tables"],
                "warnings": section["assets"]["warnings"]
            }
        }
        
        self.chunks.append(chunk)
    
    def _split_section_into_chunks(self, content, section):
        """Split section content into multiple chunks"""
        # Split content into sentences or paragraphs
        split_chars = self.chunk_settings["special_break_chars"]
        parts = []
        
        # Start with content
        current_part = ""
        
        for char in content:
            current_part += char
            
            # Check if we should split here
            if any(current_part.endswith(split_char) for split_char in split_chars):
                if len(current_part) > 0:
                    parts.append(current_part)
                    current_part = ""
        
        # Add the last part if it exists
        if current_part:
            parts.append(current_part)
        
        # Now combine parts into chunks
        chunks = []
        current_chunk = ""
        chunk_index = 0
        
        for part in parts:
            # If adding this part would exceed chunk size, save current chunk and start a new one
            if len(current_chunk) + len(part) > self.chunk_settings["chunk_size"]:
                if current_chunk:
                    # Add section header to every chunk for context
                    if not current_chunk.startswith(f"SECTION {section['id']}"):
                        current_chunk = f"SECTION {section['id']} {section['title']}\n\n{current_chunk}"
                    
                    self._add_section_chunk(current_chunk, section, chunk_index)
                    chunk_index += 1
                    
                    # Start new chunk with overlap from previous chunk
                    if self.chunk_settings["chunk_overlap"] > 0:
                        # Find a good breaking point for the overlap
                        overlap_text = current_chunk[-self.chunk_settings["chunk_overlap"]:]
                        
                        # Find the first sentence break in the overlap
                        for split_char in split_chars:
                            pos = overlap_text.find(split_char)
                            if pos > 0:
                                overlap_text = overlap_text[pos + len(split_char):]
                                break
                        
                        current_chunk = overlap_text
                    else:
                        current_chunk = ""
            
            current_chunk += part
        
        # Add the last chunk if it exists
        if current_chunk:
            # Add section header if needed
            if not current_chunk.startswith(f"SECTION {section['id']}"):
                current_chunk = f"SECTION {section['id']} {section['title']}\n\n{current_chunk}"
            
            self._add_section_chunk(current_chunk, section, chunk_index)
    
    def save_chunks(self, output_path=None):
        """
        Save chunks to file
        
        Args:
            output_path (str, optional): Path to save chunks
        
        Returns:
            str: Path to saved chunks file
        """
        if not output_path:
            output_path = PROCESSED_DIR / f"{self.document_id}_chunks.json"
        
        with open(output_path, "w") as f:
            json.dump(self.chunks, f, indent=2)
        
        logger.info(f"Saved {len(self.chunks)} chunks to {output_path}")
        
        return output_path 