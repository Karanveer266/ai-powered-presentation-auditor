# extraction.py

"""
PowerPoint content extraction with OCR support and validation.
"""

import logging
import os
import re
import asyncio
from pathlib import Path
from typing import List, Optional

from pptx import Presentation
from PIL import Image

# Note: Table class is accessed through shape.table, not imported directly
# The circular import line that was here has been removed.

logger = logging.getLogger(__name__)


class SlideDoc:
    """Represents a single slide with extracted content."""
    
    def __init__(self, slide_num: int, title: str = "", content: str = "", 
                 tables: List[str] = None, image_text: str = "", notes: str = ""):
        self.slide_num = slide_num
        self.title = title
        self.content = content
        self.tables = tables or []
        self.image_text = image_text
        self.notes = notes
    
    def get_all_text(self) -> str:
        """Get all text content from the slide."""
        all_text = []
        
        if self.title:
            all_text.append(f"Title: {self.title}")
        
        if self.content:
            all_text.append(f"Content: {self.content}")
        
        if self.tables:
            for i, table_text in enumerate(self.tables):
                all_text.append(f"Table {i+1}:\n{table_text}")
        
        if self.image_text:
            all_text.append(f"Image Text: {self.image_text}")

        if self.notes:
            all_text.append(f"Speaker Notes: {self.notes}")
        
        return "\n\n".join(all_text)
    
    def __str__(self):
        return f"Slide {self.slide_num}: {self.title[:50]}..."


def validate_inputs(pptx_path: str, img_dir: Optional[str] = None) -> None:
    """Validate input files and directories."""
    # Check PowerPoint file
    pptx_file = Path(pptx_path)
    if not pptx_file.exists():
        raise FileNotFoundError(f"PowerPoint file not found: {pptx_path}")
    
    if not pptx_file.suffix.lower() == '.pptx':
        raise ValueError(f"File must be a .pptx file: {pptx_path}")
    
    # Check image directory if provided
    if img_dir:
        img_path = Path(img_dir)
        if not img_path.exists():
            raise FileNotFoundError(f"Image directory not found: {img_dir}")
        
        if not img_path.is_dir():
            raise ValueError(f"Image path must be a directory: {img_dir}")
    
    logger.debug("Input validation passed")


async def extract_presentation_content(pptx_path: str, img_dir: Optional[str] = None, 
                                       gemini_client=None) -> List[SlideDoc]:
    """Extract comprehensive content from PowerPoint presentation asynchronously."""
    logger.info("Starting presentation content extraction")
    
    try:
        # Load PowerPoint presentation
        presentation = Presentation(pptx_path)
        slides = []
        
        for i, slide in enumerate(presentation.slides, 1):
            logger.debug(f"📄 Processing slide {i}")
            
            # Extract basic slide content
            slide_doc = extract_slide_content(slide, i)
            
            # Add OCR content from images if available and a client is provided
            if img_dir and gemini_client:
                # This now correctly awaits the async function
                image_text = await extract_slide_image_text(i, img_dir, gemini_client)
                if image_text:
                    slide_doc.image_text = image_text
            
            slides.append(slide_doc)
        
        logger.info(f"Extracted content from {len(slides)} slides")
        return slides
    
    except Exception as e:
        logger.error(f"❌ Failed to extract presentation content: {e}")
        raise


def extract_slide_content(slide, slide_num: int) -> SlideDoc:
    """Extract text content from a single slide."""
    title = ""
    content_parts = []
    tables = []
    notes = ""
    
    # Extract speaker notes
    if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
        notes = slide.notes_slide.notes_text_frame.text.strip()

    for shape in slide.shapes:
        try:
            # Extract text from text boxes and placeholders
            if hasattr(shape, "text") and shape.text.strip():
                text = clean_text(shape.text)
                
                # Try to identify title vs content
                is_title = False
                if hasattr(shape, 'placeholder_format') and shape.placeholder_format.type in [1, 13]: # Title or Centered Title
                    is_title = True
                elif shape.is_placeholder and shape.placeholder_format.idx == 0:
                    is_title = True

                if not title and is_title:
                    title = text
                else:
                    content_parts.append(text)
            
            # Extract table content
            elif hasattr(shape, 'has_table') and shape.has_table:
                table_text = extract_table_text(shape.table)
                if table_text:
                    tables.append(table_text)
        
        except Exception as e:
            logger.debug(f"Error processing shape on slide {slide_num}: {e}")
            continue
    
    # If no title was identified, use first content as title
    if not title and content_parts:
        title = content_parts.pop(0)
    
    content = "\n".join(content_parts)
    
    return SlideDoc(
        slide_num=slide_num,
        title=title,
        content=content,
        tables=tables,
        notes=notes
    )


def extract_table_text(table) -> str:
    """Extract and format text from a PowerPoint table."""
    try:
        table_rows = []
        for row in table.rows:
            row_cells = [clean_text(cell.text) for cell in row.cells]
            if any(cell.strip() for cell in row_cells):
                table_rows.append(" | ".join(row_cells))
        return "\n".join(table_rows) if table_rows else ""
    except Exception as e:
        logger.debug(f"Error extracting table: {e}")
    return ""


async def extract_slide_image_text(slide_num: int, img_dir: str, 
                                   gemini_client) -> str:
    """Extract text from slide image using OCR."""
    try:
        img_path = Path(img_dir)
        image_file = None
        for ext in ['.png', '.jpg', '.jpeg']:
            for name_format in [f"slide{slide_num}{ext}", f"Slide{slide_num}{ext}", f"slide_{slide_num}{ext}"]:
                candidate = img_path / name_format
                if candidate.exists():
                    image_file = candidate
                    break
            if image_file:
                break
        
        if not image_file:
            logger.debug(f"No image file found for slide {slide_num}")
            return ""
        
        logger.debug(f"🖼️ Extracting OCR text from {image_file}")
        image_text = await gemini_client.extract_text_from_image(str(image_file))
        
        if image_text:
            logger.debug(f"✅ Extracted {len(image_text)} characters from slide {slide_num} image")
            return clean_text(image_text)
    
    except Exception as e:
        logger.debug(f"Error extracting image text for slide {slide_num}: {e}")
    
    return ""


def clean_text(text: str) -> str:
    """Clean and normalize extracted text."""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    return text.strip()