"""
TOA-AI PDF Processor
Processes Technical Order PDFs to extract content with structure preservation
"""

import os
import re
import io
import sys
from pathlib import Path
import fitz  # PyMuPDF
import camelot
import pandas as pd
from PIL import Image
import pytesseract
from tqdm import tqdm

# Add parent directory to system path
sys.path.append(str(Path(__file__).parent.parent.parent))
from config.config import PDF_PROCESSING, DOCUMENT_STRUCTURE
from src.utils.logger import get_logger, timer
from src.utils.asset_manager import AssetManager

logger = get_logger("PDFProcessor")

class PDFProcessor:
    """
    Processes Technical Order PDFs to extract text, tables, images with structure
    """
    
    def __init__(self, pdf_path):
        """
        Initialize the PDF processor
        
        Args:
            pdf_path (str): Path to the PDF file
        """
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        self.document_id = self.pdf_path.stem
        self.doc = fitz.open(pdf_path)
        self.num_pages = len(self.doc)
        
        # Initialize asset manager
        self.asset_manager = AssetManager(self.document_id)
        
        # Compiled regex patterns
        self._compile_patterns()
        
        # Tesseract config
        if hasattr(PDF_PROCESSING, "tesseract_path") and PDF_PROCESSING["tesseract_path"]:
            pytesseract.pytesseract.tesseract_cmd = PDF_PROCESSING["tesseract_path"]
        
        logger.info(f"Initialized PDF processor for {self.pdf_path.name} ({self.num_pages} pages)")
    
    def _compile_patterns(self):
        """Compile regex patterns for faster matching"""
        # Section patterns
        self.section_patterns = [re.compile(pattern) for pattern in DOCUMENT_STRUCTURE["section_patterns"]]
        
        # Warning patterns
        self.warning_patterns = [re.compile(pattern, re.DOTALL) for pattern in DOCUMENT_STRUCTURE["warning_patterns"]]
        
        # Figure and table patterns
        self.figure_patterns = [re.compile(pattern) for pattern in DOCUMENT_STRUCTURE["figure_patterns"]]
        self.table_patterns = [re.compile(pattern) for pattern in DOCUMENT_STRUCTURE["table_patterns"]]
        
        # Other patterns
        self.afto_form_pattern = re.compile(DOCUMENT_STRUCTURE["afto_form_pattern"])
        self.to_number_pattern = re.compile(DOCUMENT_STRUCTURE["to_number_pattern"])
    
    def _rect_to_list(self, rect):
        """Convert a fitz.Rect to a list for JSON serialization"""
        if rect is None:
            return None
        return [rect.x0, rect.y0, rect.x1, rect.y1]
    
    @timer
    def process_document(self):
        """
        Process the entire document and return structured content
        
        Returns:
            dict: Structured document content
        """
        # Extract metadata first
        metadata = self._extract_metadata()
        
        # Initialize document structure
        document = {
            "id": self.document_id,
            "metadata": metadata,
            "sections": [],
            "asset_counts": {
                "images": 0,
                "tables": 0,
                "warnings": 0
            }
        }
        
        # Process each page
        for page_num in tqdm(range(self.num_pages), desc=f"Processing {self.document_id}"):
            page_content = self._process_page(page_num)
            
            # Update document with page content
            document["sections"].extend(page_content.get("sections", []))
            document["asset_counts"]["images"] += len(page_content.get("images", []))
            document["asset_counts"]["tables"] += len(page_content.get("tables", []))
            document["asset_counts"]["warnings"] += len(page_content.get("warnings", []))
        
        # Link sections to their parent sections
        self._link_sections(document["sections"])
        
        logger.info(f"Processed document {self.document_id}: "
                   f"{len(document['sections'])} sections, "
                   f"{document['asset_counts']['images']} images, "
                   f"{document['asset_counts']['tables']} tables, "
                   f"{document['asset_counts']['warnings']} warnings")
        
        return document
    
    def _extract_metadata(self):
        """
        Extract document metadata from the first few pages
        
        Returns:
            dict: Document metadata
        """
        # Get text from first page
        first_page_text = self.doc[0].get_text()
        
        # Extract TO number
        to_match = self.to_number_pattern.search(first_page_text)
        to_number = to_match.group(1) if to_match else "Unknown"
        
        # Try to extract title (usually follows TO number)
        title = "Unknown"
        if to_match:
            # Look for title pattern after TO number
            title_end_pos = first_page_text.find("\n\n", to_match.end())
            if title_end_pos > 0:
                title_candidate = first_page_text[to_match.end():title_end_pos].strip()
                if len(title_candidate) > 3:  # Minimum reasonable title length
                    title = title_candidate
        
        # Check for classification markings
        classification = "UNCLASSIFIED"
        if re.search(r'CONFIDENTIAL', first_page_text, re.IGNORECASE):
            classification = "CONFIDENTIAL"
        elif re.search(r'SECRET', first_page_text, re.IGNORECASE):
            classification = "SECRET"
        elif re.search(r'TOP SECRET', first_page_text, re.IGNORECASE):
            classification = "TOP SECRET"
        
        # Try to extract date
        date_match = re.search(r'(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})', 
                              first_page_text)
        date = date_match.group(1) if date_match else None
        
        # Look for revision information
        revision_match = re.search(r'(?:Revision|Rev\.)\s+(\d+|[A-Z])', first_page_text, re.IGNORECASE)
        revision = revision_match.group(1) if revision_match else None
        
        return {
            "to_number": to_number,
            "title": title,
            "classification": classification,
            "date": date,
            "revision": revision,
            "pages": self.num_pages,
            "filename": self.pdf_path.name
        }
    
    @timer
    def _process_page(self, page_num):
        """
        Process a single page of the document
        
        Args:
            page_num (int): Page number to process (0-indexed)
            
        Returns:
            dict: Structured page content
        """
        page = self.doc[page_num]
        
        # Extract basic text content
        text = page.get_text()
        
        # Check if page needs OCR (insufficient text)
        if len(text.strip()) < PDF_PROCESSING["min_text_length"]:
            logger.info(f"Page {page_num+1} has insufficient text, attempting OCR")
            text = self._apply_ocr(page)
        
        # Extract sections from text
        sections = self._extract_sections(text, page_num)
        
        # Extract warnings and cautions
        warnings = self._extract_warnings(text, page_num)
        
        # Extract tables
        tables = self._extract_tables(page_num)
        
        # Extract images
        images = self._extract_images(page, page_num)
        
        # Link sections with assets
        self._link_sections_with_assets(sections, images, tables, warnings)
        
        return {
            "page_num": page_num,
            "sections": sections,
            "images": images,
            "tables": tables,
            "warnings": warnings
        }
    
    def _extract_sections(self, text, page_num):
        """
        Extract sections from text content
        
        Args:
            text (str): Text content
            page_num (int): Page number
            
        Returns:
            list: Extracted sections
        """
        sections = []
        lines = text.split('\n')
        
        current_section = None
        section_content = []
        
        for line in lines:
            section_match = None
            
            # Try each section pattern
            for pattern in self.section_patterns:
                match = pattern.match(line)
                if match:
                    section_match = match
                    break
            
            if section_match:
                # Save current section if exists
                if current_section:
                    current_section["content"] = '\n'.join(section_content).strip()
                    sections.append(current_section)
                    section_content = []
                
                # Extract section ID and title
                if len(section_match.groups()) == 2:
                    section_id, section_title = section_match.groups()
                else:  # For patterns with chapter/section prefix
                    prefix, section_id, section_title = section_match.groups()
                    section_id = f"{prefix} {section_id}"
                
                # Create new section
                current_section = {
                    "id": section_id.strip(),
                    "title": section_title.strip(),
                    "page": page_num + 1,
                    "content": "",
                    "parent_id": None,
                    "level": self._calculate_section_level(section_id),
                    "assets": {
                        "images": [],
                        "tables": [],
                        "warnings": []
                    }
                }
            else:
                # Add line to current section content
                if current_section:
                    section_content.append(line)
        
        # Add the last section
        if current_section:
            current_section["content"] = '\n'.join(section_content).strip()
            sections.append(current_section)
        
        return sections
    
    def _calculate_section_level(self, section_id):
        """
        Calculate the section level based on its ID
        
        Args:
            section_id (str): Section identifier
            
        Returns:
            int: Section level (1, 2, 3, etc.)
        """
        # Remove any non-numeric prefix
        numeric_part = re.sub(r'^(?:CHAPTER|SECTION)\s+', '', section_id)
        
        # Count the number of dot-separated components
        components = numeric_part.split('.')
        return len(components)
    
    def _extract_warnings(self, text, page_num):
        """
        Extract warnings, cautions, and notes from text
        
        Args:
            text (str): Text content
            page_num (int): Page number
            
        Returns:
            list: Extracted warnings
        """
        warnings = []
        
        # Try each warning pattern
        for pattern in self.warning_patterns:
            matches = pattern.finditer(text)
            
            for match in matches:
                warning_type = match.group(1).upper()
                content = match.group(2).strip()
                
                # Store warning in asset manager
                warning_id = self.asset_manager.store_warning(
                    warning_type, 
                    content, 
                    page_num
                )
                
                if warning_id:
                    warnings.append({
                        "id": warning_id,
                        "type": warning_type,
                        "content": content,
                        "page": page_num + 1
                    })
        
        return warnings
    
    @timer
    def _extract_tables(self, page_num):
        """
        Extract tables from the page
        
        Args:
            page_num (int): Page number
            
        Returns:
            list: Extracted tables
        """
        tables = []
        
        # Try to extract tables with Camelot
        try:
            # First try lattice mode (for bordered tables)
            lattice_tables = camelot.read_pdf(
                str(self.pdf_path), 
                pages=str(page_num + 1), 
                flavor='lattice'
            )
            
            # If lattice mode found tables, use those
            if len(lattice_tables) > 0 and lattice_tables[0].shape[0] > 0:
                logger.info(f"Found {len(lattice_tables)} table(s) with lattice mode on page {page_num+1}")
                
                for i, table in enumerate(lattice_tables):
                    if table.shape[0] > 0:  # Only process non-empty tables
                        # Look for table caption
                        caption = self._find_table_caption(page_num)
                        
                        # Store table in asset manager
                        table_id = self.asset_manager.store_table(
                            table.df, 
                            page_num,
                            caption=caption,
                            table_num=f"Table {i+1}"
                        )
                        
                        if table_id:
                            tables.append({
                                "id": table_id,
                                "page": page_num + 1,
                                "caption": caption,
                                "rows": table.shape[0],
                                "columns": table.shape[1]
                            })
            else:
                # If lattice mode failed, try stream mode (for borderless tables)
                stream_tables = camelot.read_pdf(
                    str(self.pdf_path), 
                    pages=str(page_num + 1), 
                    flavor='stream'
                )
                
                logger.info(f"Found {len(stream_tables)} table(s) with stream mode on page {page_num+1}")
                
                for i, table in enumerate(stream_tables):
                    if table.shape[0] > 0:  # Only process non-empty tables
                        # Look for table caption
                        caption = self._find_table_caption(page_num)
                        
                        # Store table in asset manager
                        table_id = self.asset_manager.store_table(
                            table.df, 
                            page_num,
                            caption=caption,
                            table_num=f"Table {i+1}"
                        )
                        
                        if table_id:
                            tables.append({
                                "id": table_id,
                                "page": page_num + 1,
                                "caption": caption,
                                "rows": table.shape[0],
                                "columns": table.shape[1]
                            })
                            
        except Exception as e:
            logger.error(f"Error extracting tables from page {page_num+1}: {str(e)}")
        
        return tables
    
    def _find_table_caption(self, page_num):
        """Find table caption on the page"""
        text = self.doc[page_num].get_text()
        
        for pattern in self.table_patterns:
            match = pattern.search(text)
            if match:
                if len(match.groups()) >= 2:
                    table_num, caption = match.groups()
                    return caption.strip()
                elif len(match.groups()) == 1:
                    return match.group(1).strip()
        
        return None
    
    @timer
    def _extract_images(self, page, page_num):
        """
        Extract images from the page
        
        Args:
            page (fitz.Page): Page object
            page_num (int): Page number
            
        Returns:
            list: Extracted images
        """
        images = []
        
        # Get image list from page
        img_list = page.get_images(full=True)
        
        for img_index, img in enumerate(img_list):
            xref = img[0]
            
            try:
                # Extract image
                base_image = self.doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # Try to find caption
                caption = self._find_image_caption(page_num)
                
                # Extract image rectangle
                rect = None
                for img_rect in page.get_image_rects(xref):
                    # Convert Rect to list to make it JSON serializable
                    rect = self._rect_to_list(img_rect)
                    break
                
                # Store image in asset manager
                image_id = self.asset_manager.store_image(
                    image_bytes,
                    page_num,
                    caption=caption,
                    source_rect=rect
                )
                
                if image_id:
                    images.append({
                        "id": image_id,
                        "page": page_num + 1,
                        "caption": caption
                    })
                    
            except Exception as e:
                logger.error(f"Error extracting image {img_index} from page {page_num+1}: {str(e)}")
        
        return images
    
    def _find_image_caption(self, page_num):
        """Find image caption on the page"""
        text = self.doc[page_num].get_text()
        
        for pattern in self.figure_patterns:
            match = pattern.search(text)
            if match:
                if len(match.groups()) >= 2:
                    figure_num, caption = match.groups()
                    return caption.strip()
                elif len(match.groups()) == 1:
                    return match.group(1).strip()
        
        return None
        
    def _apply_ocr(self, page):
        """
        Apply OCR to a page for text extraction
        
        Args:
            page (fitz.Page): Page object
            
        Returns:
            str: Extracted text
        """
        # Convert page to image
        pix = page.get_pixmap(dpi=PDF_PROCESSING["dpi"])
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Apply OCR
        text = pytesseract.image_to_string(
            img, 
            lang=PDF_PROCESSING["ocr_lang"]
        )
        
        return text
    
    def _link_sections_with_assets(self, sections, images, tables, warnings):
        """
        Link sections with their associated assets
        
        Args:
            sections (list): List of sections
            images (list): List of images
            tables (list): List of tables
            warnings (list): List of warnings
        """
        # Link assets to sections based on proximity
        for section in sections:
            # Link all assets on the same page
            section_page = section["page"] - 1  # Convert to 0-indexed
            
            for image in images:
                if image["page"] - 1 == section_page:
                    section["assets"]["images"].append(image["id"])
            
            for table in tables:
                if table["page"] - 1 == section_page:
                    section["assets"]["tables"].append(table["id"])
            
            for warning in warnings:
                if warning["page"] - 1 == section_page:
                    # Check if warning text is in section content
                    if warning["content"] in section["content"]:
                        section["assets"]["warnings"].append(warning["id"])
                        
                        # Also update the warning with its section ID
                        warning_obj = self.asset_manager.get_warning(warning["id"])
                        if warning_obj:
                            warning_obj["section_id"] = section["id"]
                            # Note: We'd need to save the registry if we want this to persist
    
    def _link_sections(self, sections):
        """
        Link sections to their parent sections
        
        Args:
            sections (list): List of sections
        """
        # Sort sections by ID for easier linking
        sections.sort(key=lambda s: s["id"])
        
        # For each section, find its potential parent
        for i, section in enumerate(sections):
            section_id = section["id"]
            section_level = section["level"]
            
            # Skip if it's a top-level section
            if section_level <= 1:
                continue
                
            # Look for parent (search backwards)
            for j in range(i - 1, -1, -1):
                potential_parent = sections[j]
                
                # Parent must have lower level
                if potential_parent["level"] < section_level:
                    # Check if section ID starts with parent ID
                    if section_id.startswith(potential_parent["id"].split()[0]):
                        section["parent_id"] = potential_parent["id"]
                        break 