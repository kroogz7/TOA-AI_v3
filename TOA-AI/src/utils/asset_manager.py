"""
TOA-AI Asset Manager
Manages the extraction and storage of assets from PDFs
"""

import os
import io
import uuid
import json
import base64
import hashlib
from pathlib import Path
import pandas as pd
import numpy as np
from PIL import Image

import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.config import ASSETS_DIR, IMAGE_DIR, TABLE_DIR, WARNING_DIR
from src.utils.logger import get_logger, timer

logger = get_logger("AssetManager")

class AssetManager:
    """
    Manages the extraction, storage, and retrieval of assets from PDFs
    Assets include: images, tables, warnings, etc.
    """
    
    def __init__(self, document_id):
        """
        Initialize the asset manager for a specific document
        
        Args:
            document_id (str): Unique identifier for the document
        """
        self.document_id = document_id
        
        # Create document-specific asset directories
        self.doc_asset_dir = ASSETS_DIR / document_id
        self.doc_image_dir = IMAGE_DIR / document_id
        self.doc_table_dir = TABLE_DIR / document_id
        self.doc_warning_dir = WARNING_DIR / document_id
        
        # Ensure directories exist
        for dir_path in [self.doc_asset_dir, self.doc_image_dir, 
                         self.doc_table_dir, self.doc_warning_dir]:
            os.makedirs(dir_path, exist_ok=True)
        
        # Initialize asset registries
        self.image_registry = {}
        self.table_registry = {}
        self.warning_registry = {}
        
        # Load existing registries if they exist
        self._load_registries()
    
    def _load_registries(self):
        """Load existing asset registries if they exist"""
        registry_path = self.doc_asset_dir / "asset_registry.json"
        if os.path.exists(registry_path):
            try:
                with open(registry_path, "r") as f:
                    registry = json.load(f)
                    self.image_registry = registry.get("images", {})
                    self.table_registry = registry.get("tables", {})
                    self.warning_registry = registry.get("warnings", {})
                logger.info(f"Loaded existing asset registry for {self.document_id}")
            except Exception as e:
                logger.error(f"Error loading asset registry: {e}")
    
    def _save_registries(self):
        """Save asset registries to disk"""
        registry = {
            "images": self.image_registry,
            "tables": self.table_registry,
            "warnings": self.warning_registry
        }
        
        registry_path = self.doc_asset_dir / "asset_registry.json"
        with open(registry_path, "w") as f:
            json.dump(registry, f, indent=2)
        
        logger.info(f"Saved asset registry for {self.document_id}")
    
    def _generate_asset_id(self, asset_type, content, page_num):
        """
        Generate a unique ID for an asset
        
        Args:
            asset_type (str): Type of asset (image, table, warning)
            content: Content of the asset to hash
            page_num (int): Page number where the asset appears
            
        Returns:
            str: Unique asset ID
        """
        if isinstance(content, bytes):
            content_hash = hashlib.md5(content).hexdigest()[:8]
        elif isinstance(content, str):
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:8]
        elif isinstance(content, (pd.DataFrame, np.ndarray)):
            content_hash = hashlib.md5(str(content).encode('utf-8')).hexdigest()[:8]
        else:
            # Generate a random UUID if content can't be hashed
            content_hash = str(uuid.uuid4())[:8]
        
        return f"{asset_type}_{self.document_id}_p{page_num}_{content_hash}"
    
    def _clean_text(self, text):
        """Clean text to ensure it can be saved properly"""
        if not isinstance(text, str):
            return text
        
        # Replace special ligatures and other problematic characters
        replacements = {
            '\ufb01': 'fi',  # fi ligature
            '\ufb02': 'fl',  # fl ligature
            '\u2019': "'",   # right single quotation mark
            '\u2018': "'",   # left single quotation mark
            '\u201c': '"',   # left double quotation mark
            '\u201d': '"',   # right double quotation mark
            '\u2013': '-',   # en dash
            '\u2014': '--',  # em dash
        }
        
        for char, replacement in replacements.items():
            text = text.replace(char, replacement)
            
        return text
    
    @timer
    def store_image(self, image_data, page_num, caption=None, source_rect=None):
        """
        Store an image asset
        
        Args:
            image_data (bytes or PIL.Image): Image data
            page_num (int): Page number where the image appears
            caption (str, optional): Caption for the image
            source_rect (tuple, optional): Source rectangle (x0, y0, x1, y1)
            
        Returns:
            str: Image asset ID
        """
        # Generate asset ID
        image_id = self._generate_asset_id("img", image_data, page_num)
        
        # Convert to PIL Image if needed
        if isinstance(image_data, bytes):
            try:
                image = Image.open(io.BytesIO(image_data))
            except Exception as e:
                logger.error(f"Error opening image data: {e}")
                return None
        elif isinstance(image_data, Image.Image):
            image = image_data
        else:
            logger.error(f"Unsupported image data type: {type(image_data)}")
            return None
        
        # Save image to file
        image_path = self.doc_image_dir / f"{image_id}.png"
        try:
            image.save(image_path)
        except Exception as e:
            logger.error(f"Error saving image: {e}")
            return None
        
        # Register image
        self.image_registry[image_id] = {
            "id": image_id,
            "document_id": self.document_id,
            "page_num": page_num,
            "caption": caption,
            "source_rect": source_rect,
            "file_path": str(image_path),
            "width": image.width,
            "height": image.height,
            "format": image.format
        }
        
        # Save registry
        self._save_registries()
        
        logger.info(f"Stored image asset: {image_id}")
        return image_id
    
    @timer
    def store_table(self, table_data, page_num, caption=None, table_num=None):
        """
        Store a table asset
        
        Args:
            table_data (pandas.DataFrame or dict): Table data
            page_num (int): Page number where the table appears
            caption (str, optional): Caption for the table
            table_num (str, optional): Table number/identifier from the document
            
        Returns:
            str: Table asset ID
        """
        # Convert dictionary to DataFrame if needed
        if isinstance(table_data, dict):
            table_df = pd.DataFrame.from_dict(table_data)
        elif isinstance(table_data, pd.DataFrame):
            table_df = table_data
        else:
            logger.error(f"Unsupported table data type: {type(table_data)}")
            return None
        
        # Clean table data to avoid encoding issues
        for col in table_df.columns:
            if table_df[col].dtype == 'object':  # Only process string columns
                table_df[col] = table_df[col].apply(lambda x: self._clean_text(x) if isinstance(x, str) else x)
        
        # Generate asset ID
        table_id = self._generate_asset_id("tbl", table_df, page_num)
        
        # Save table to files (CSV and markdown)
        csv_path = self.doc_table_dir / f"{table_id}.csv"
        md_path = self.doc_table_dir / f"{table_id}.md"
        
        try:
            # Save as CSV
            table_df.to_csv(csv_path, index=False)
            
            # Save as markdown
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(table_df.to_markdown(index=False))
            
            # Generate HTML preview
            html = table_df.to_html(index=False)
        except Exception as e:
            logger.error(f"Error saving table: {str(e)}")
            return None
        
        # Register table
        self.table_registry[table_id] = {
            "id": table_id,
            "document_id": self.document_id,
            "page_num": page_num,
            "caption": self._clean_text(caption),
            "table_num": table_num,
            "csv_path": str(csv_path),
            "md_path": str(md_path),
            "rows": table_df.shape[0],
            "columns": table_df.shape[1],
            "headers": table_df.columns.tolist(),
        }
        
        # Save registry
        self._save_registries()
        
        logger.info(f"Stored table asset: {table_id}")
        return table_id
    
    @timer
    def store_warning(self, warning_type, content, page_num, section_id=None):
        """
        Store a warning/caution/note asset
        
        Args:
            warning_type (str): Type of warning (WARNING, CAUTION, NOTE)
            content (str): Warning content
            page_num (int): Page number where the warning appears
            section_id (str, optional): ID of the section containing the warning
            
        Returns:
            str: Warning asset ID
        """
        # Clean content to avoid encoding issues
        content = self._clean_text(content)
        
        # Generate asset ID
        warning_id = self._generate_asset_id("warn", content, page_num)
        
        # Normalize warning type
        warning_type = warning_type.upper()
        if warning_type not in ["WARNING", "CAUTION", "NOTE"]:
            logger.warning(f"Unusual warning type: {warning_type}, normalizing to WARNING")
            warning_type = "WARNING"
        
        # Save warning to file
        warning_path = self.doc_warning_dir / f"{warning_id}.txt"
        try:
            with open(warning_path, "w", encoding="utf-8") as f:
                f.write(f"{warning_type}: {content}")
        except Exception as e:
            logger.error(f"Error saving warning: {str(e)}")
            return None
        
        # Register warning
        self.warning_registry[warning_id] = {
            "id": warning_id,
            "document_id": self.document_id,
            "page_num": page_num,
            "warning_type": warning_type,
            "content": content,
            "section_id": section_id,
            "file_path": str(warning_path),
            # Priority: WARNING > CAUTION > NOTE
            "priority": {"WARNING": 1, "CAUTION": 2, "NOTE": 3}.get(warning_type, 4)
        }
        
        # Save registry
        self._save_registries()
        
        logger.info(f"Stored {warning_type} asset: {warning_id}")
        return warning_id
    
    def get_image(self, image_id):
        """Get image metadata by ID"""
        return self.image_registry.get(image_id)
    
    def get_table(self, table_id):
        """Get table metadata by ID"""
        return self.table_registry.get(table_id)
    
    def get_warning(self, warning_id):
        """Get warning metadata by ID"""
        return self.warning_registry.get(warning_id)
    
    def get_all_assets(self):
        """Get all assets for the document"""
        return {
            "images": self.image_registry,
            "tables": self.table_registry,
            "warnings": self.warning_registry
        }
    
    def get_page_assets(self, page_num):
        """Get all assets for a specific page"""
        page_assets = {
            "images": {},
            "tables": {},
            "warnings": {}
        }
        
        for img_id, img in self.image_registry.items():
            if img["page_num"] == page_num:
                page_assets["images"][img_id] = img
                
        for tbl_id, tbl in self.table_registry.items():
            if tbl["page_num"] == page_num:
                page_assets["tables"][tbl_id] = tbl
                
        for warn_id, warn in self.warning_registry.items():
            if warn["page_num"] == page_num:
                page_assets["warnings"][warn_id] = warn
        
        return page_assets 