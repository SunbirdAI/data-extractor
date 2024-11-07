"""
PDF processing module for ACRES RAG Platform.
Handles PDF file processing, text extraction, and page rendering.
"""

# utils/pdf_processor.py
import os
import fitz
import logging
from typing import Dict, List, Optional
import datetime
from slugify import slugify
import json
from PIL import Image


logger = logging.getLogger(__name__)


class PDFProcessor:
    def __init__(self, upload_dir: str = "data/uploads"):
        """Initialize PDFProcessor with upload directory."""
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)
        self.current_page = 0

    def render_page(self, file_path: str, page_num: int) -> Optional[Image.Image]:
        """Render a specific page from a PDF as an image."""
        try:
            logger.info(f"Attempting to render page {page_num} from {file_path}")
            doc = fitz.open(file_path)

            # Ensure page number is valid
            if page_num < 0 or page_num >= len(doc):
                logger.error(
                    f"Invalid page number {page_num} for document with {len(doc)} pages"
                )
                return None

            page = doc[page_num]
            # Increase resolution for better quality
            pix = page.get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72))
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()
            logger.info(f"Successfully rendered page {page_num}")
            return image
        except Exception as e:
            logger.error(f"Error rendering page {page_num} from {file_path}: {str(e)}")
            return None

    def process_pdfs(self, file_paths: List[str], collection_name: str) -> str:
        """Process multiple PDF files and store their content."""
        processed_docs = []

        for file_path in file_paths:
            try:
                doc_data = self.extract_text_from_pdf(file_path)
                processed_docs.append(doc_data)
                logger.info(f"Successfully processed {file_path}")
            except Exception as e:
                logger.error(f"Error processing {file_path}: {str(e)}")
                continue

        if not processed_docs:
            raise ValueError("No documents were successfully processed")

        # Save to JSON file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"{slugify(collection_name)}_{timestamp}_documents.json"
        output_path = os.path.join("data", output_filename)

        # Ensure the data directory exists
        os.makedirs("data", exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(processed_docs, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved processed documents to {output_path}")
        return output_path

    def extract_text_from_pdf(self, file_path: str) -> Dict:
        """Extract text and metadata from a PDF file."""
        try:
            doc = fitz.open(file_path)

            # Extract text from all pages with page tracking
            text = ""
            pages = {}
            for page_num in range(len(doc)):
                page_text = doc[page_num].get_text()
                pages[str(page_num)] = page_text  # Convert page_num to string for JSON
                text += page_text + "\n"

            # Extract metadata
            metadata = doc.metadata
            if not metadata.get("title"):
                metadata["title"] = os.path.basename(file_path)

            # Create structured document
            document = {
                "title": metadata.get("title", ""),
                "authors": (
                    metadata.get("author", "").split(";")
                    if metadata.get("author")
                    else []
                ),
                "date": metadata.get("creationDate", ""),
                "abstract": text[:500] + "..." if len(text) > 500 else text,
                "full_text": text,
                "source_file": file_path,
                "pages": pages,
                "page_count": len(doc),
            }

            doc.close()
            return document
        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {str(e)}")
            raise
