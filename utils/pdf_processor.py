# utils/pdf_processor.py

"""
PDF processing module for ACRES RAG Platform.
Handles PDF file processing, text extraction, and page rendering.
"""

import datetime
import json
import logging
import os
import re
from typing import Dict, List, Optional

import fitz
from llama_index.readers.docling import DoclingReader
from PIL import Image
from slugify import slugify

logger = logging.getLogger(__name__)


reader = DoclingReader()


class PDFProcessor:
    def __init__(self, upload_dir: str = "data/uploads"):
        """Initialize PDFProcessor with upload directory."""
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)
        self.current_page = 0

    def is_references_page(self, text: str) -> bool:
        """
        Check if the page appears to be a references/bibliography page.
        """
        # Common section headers for references
        ref_headers = [
            r"^references\s*$",
            r"^bibliography\s*$",
            r"^works cited\s*$",
            r"^citations\s*$",
            r"^cited literature\s*$",
        ]

        # Check first few lines of the page
        first_lines = text.lower().split("\n")[:3]
        first_block = " ".join(first_lines)

        # Check for reference headers
        for header in ref_headers:
            if re.search(header, first_block, re.IGNORECASE):
                return True

        # Check for reference-like patterns (e.g., [1] Author, et al.)
        ref_patterns = [
            r"^\[\d+\]",  # [1] style
            r"^\d+\.",  # 1. style
            r"^[A-Z][a-z]+,\s+[A-Z]\.",  # Author, I. style
        ]

        ref_pattern_count = 0
        lines = text.split("\n")[:10]  # Check first 10 lines
        for line in lines:
            line = line.strip()
            if any(re.match(pattern, line) for pattern in ref_patterns):
                ref_pattern_count += 1

        # If multiple reference-like patterns are found, likely a references page
        return ref_pattern_count >= 3

    def detect_references_start(self, doc: fitz.Document) -> Optional[int]:
        """
        Detect the page where references section starts.
        Returns the page number or None if not found.
        """
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            if self.is_references_page(text):
                logger.info(f"Detected references section starting at page {page_num}")
                return page_num
        return None

    def process_pdfs(self, file_paths: List[str], collection_name: str) -> str:
        """Process multiple PDF files and store their content."""
        processed_docs = []

        for file_path in file_paths:
            try:
                doc_data = self.extract_text_from_pdf(file_path)
                processed_docs.append(doc_data)
                logger.info(
                    f"Successfully processed {file_path} ({doc_data['content_pages']} content pages)"
                )
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
        """
        Extract text and metadata from a PDF file using DoclingReader.
        Maintains accurate page numbers for source citation.
        """
        try:
            # Use DoclingReader for main content extraction
            reader = DoclingReader()
            documents = reader.load_data(file_path)
            text = documents[0].text if documents else ""

            # Use PyMuPDF to get accurate page count
            doc = fitz.open(file_path)
            total_pages = len(doc)

            # Extract title from document
            title = os.path.basename(file_path)
            title_match = re.search(r"#+ (.+?)\n", text)
            if title_match:
                title = title_match.group(1).strip()

            # Extract abstract
            abstract = ""
            abstract_match = re.search(
                r"Abstract:?(.*?)(?=\n\n|Keywords:|$)", text, re.DOTALL | re.IGNORECASE
            )
            if abstract_match:
                abstract = abstract_match.group(1).strip()

            # Extract authors
            authors = []
            author_section = re.search(r"\n(.*?)\n.*?Department", text)
            if author_section:
                author_text = author_section.group(1)
                authors = [a.strip() for a in author_text.split(",") if a.strip()]

            # Remove references section
            content = text
            ref_patterns = [r"\nReferences\n", r"\nBibliography\n", r"\nWorks Cited\n"]
            for pattern in ref_patterns:
                split_text = re.split(pattern, content, flags=re.IGNORECASE)
                if len(split_text) > 1:
                    content = split_text[0]
                    break

            # Map content to pages using PyMuPDF for accurate page numbers
            pages = {}
            for page_num in range(total_pages):
                page = doc[page_num]
                page_text = page.get_text()

                # Skip if this appears to be a references page
                if self.is_references_page(page_text):
                    logger.info(f"Skipping references page {page_num}")
                    continue

                # Look for this page's content in the Docling-extracted text
                # This is a heuristic approach - we look for unique phrases from the page
                key_phrases = self._get_key_phrases(page_text)
                page_content = self._find_matching_content(content, key_phrases)

                if page_content:
                    pages[str(page_num)] = {
                        "text": page_content,
                        "page_number": page_num
                        + 1,  # 1-based page numbers for human readability
                    }

            # Create structured document with page-aware content
            document = {
                "title": title,
                "authors": authors,
                "date": "",  # Could be extracted if needed
                "abstract": abstract,
                "full_text": content,
                "source_file": file_path,
                "pages": pages,
                "page_count": total_pages,
                "content_pages": len(pages),  # Number of non-reference pages
            }

            doc.close()
            return document

        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {str(e)}")
            raise

    def _get_key_phrases(self, text: str, phrase_length: int = 10) -> List[str]:
        """Extract key phrases from text for matching."""
        words = text.split()
        phrases = []
        for i in range(0, len(words), phrase_length):
            phrase = " ".join(words[i : i + phrase_length])
            if len(phrase.strip()) > 20:  # Only use substantial phrases
                phrases.append(phrase)
        return phrases

    def _find_matching_content(
        self, docling_text: str, key_phrases: List[str]
    ) -> Optional[str]:
        """Find the corresponding content in Docling text using key phrases."""
        for phrase in key_phrases:
            if phrase in docling_text:
                # Find the paragraph or section containing this phrase
                paragraphs = docling_text.split("\n\n")
                for para in paragraphs:
                    if phrase in para:
                        return para
        return None
