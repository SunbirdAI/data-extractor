# utils/pdf_processor.py

import datetime
import json
import logging
import os
import re
from typing import Dict, List, Optional

import fitz
from langchain import PromptTemplate
from langchain.chains.summarize import load_summarize_chain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_openai import ChatOpenAI
from slugify import slugify

logger = logging.getLogger(__name__)


def load_document(file: str) -> Optional[List]:
    """Load document using appropriate loader based on file extension."""
    loaders = {".pdf": PyPDFLoader, ".docx": Docx2txtLoader, ".txt": TextLoader}

    extension = os.path.splitext(file)[1].lower()
    if extension not in loaders:
        raise ValueError(f"Unsupported document format: {extension}")

    print(f"Loading {file}")
    loader = loaders[extension](file)
    return loader.load()


def chunk_data(data, chunk_size=256, chunk_overlap=20):
    """Split document into chunks for processing."""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunks = text_splitter.split_documents(data)
    return chunks


class PDFProcessor:
    def __init__(self, upload_dir: str = "data/uploads"):
        self.upload_dir = upload_dir
        self.var_list = []
        self.formatted_vars = ""
        os.makedirs(upload_dir, exist_ok=True)

    def is_references_page(self, text: str) -> bool:
        """Check if the page appears to be a references/bibliography page."""
        ref_headers = [
            r"^references\s*$",
            r"^bibliography\s*$",
            r"^works cited\s*$",
            r"^citations\s*$",
            r"^cited literature\s*$",
        ]

        first_lines = text.lower().split("\n")[:3]
        first_block = " ".join(first_lines)

        for header in ref_headers:
            if re.search(header, first_block, re.IGNORECASE):
                return True

        ref_patterns = [
            r"^\[\d+\]",  # [1] style
            r"^\d+\.",  # 1. style
            r"^[A-Z][a-z]+,\s+[A-Z]\.",  # Author, I. style
        ]

        ref_pattern_count = 0
        lines = text.split("\n")[:10]
        for line in lines:
            line = line.strip()
            if any(re.match(pattern, line) for pattern in ref_patterns):
                ref_pattern_count += 1

        return ref_pattern_count >= 3

    def prepare_variables(self, variables: str):
        """Prepare variables for processing."""
        if variables:
            # Clean and format variable names
            self.var_list = [v.strip().upper() for v in variables.split(",")]
            self.formatted_vars = "\n".join(f"- {var}" for var in self.var_list)
        else:
            self.var_list = []
            self.formatted_vars = ""

    def process_pdfs(
        self, file_paths: List[str], collection_name: str, variables: str = ""
    ) -> str:
        """Process multiple PDF files and store their content."""
        # Prepare variables
        self.prepare_variables(variables)

        processed_docs = []
        chunk_size = 10000
        chunk_overlap = 100

        for file_path in file_paths:
            try:
                # Load and chunk the document
                pdf_data = load_document(file_path)
                pdf_chunks = chunk_data(
                    pdf_data, chunk_size=chunk_size, chunk_overlap=chunk_overlap
                )

                # Generate summary using the stuff chain
                output_summary = self.summarize_document(pdf_chunks, variables)

                # Extract JSON data
                try:
                    json_data = self.extract_json_from_text(
                        output_summary["output_text"]
                    )
                except ValueError:
                    # If JSON extraction fails, create a basic structure
                    json_data = self.create_basic_document_structure(
                        file_path, pdf_data
                    )

                processed_docs.append(json_data)
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

        os.makedirs("data", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(processed_docs, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved processed documents to {output_path}")
        return output_path

    def summarize_document(self, chunks, variables):
        """Summarize document using the stuff chain."""
        if variables:
            # Create a structured extraction prompt based on provided variables
            template = """Extract specific information from the following text for each requested variable.

Text: {text}

For each of these variables, extract the relevant information:
{variables}

Format your response as a JSON object with these exact variable names as keys.
If a variable's information cannot be found, use null as its value.

Example format:
```json
{{
    "VARIABLE_1": "extracted value 1",
    "VARIABLE_2": "extracted value 2",
    "VARIABLE_3": null
}}
```

IMPORTANT: 
- Ensure all requested variables are included in the JSON output
- Use exact variable names as provided
- Return ONLY the JSON object
"""
        else:
            # Default template for general summarization
            template = """Extract key information from the following text:

Text: {text}

Please provide a structured summary including:
- Title of the document
- Main research objectives
- Methodology used
- Key findings
- Conclusions

Format your response as a JSON object with these standard fields.
Skip the References section when generating the summary.
"""

        prompt = PromptTemplate(
            template=template,
            input_variables=["text", "variables"] if variables else ["text"],
        )

        llm = ChatOpenAI(temperature=0, model_name="gpt-4o-mini")
        chain = load_summarize_chain(
            llm, chain_type="stuff", prompt=prompt, verbose=False
        )

        # Prepare chain input
        chain_input = {"input_documents": chunks}

        # If variables are provided, add them to the chain input
        if variables:
            chain_input["variables"] = self.formatted_vars

        response = chain.invoke(chain_input)

        # Ensure the JSON response includes all requested variables
        if variables and "output_text" in response:
            try:
                json_data = self.extract_json_from_text(response["output_text"])
                # Add any missing variables with null values
                for var in self.var_list:
                    if var not in json_data:
                        json_data[var] = None
                # Re-format the response with the complete variable set
                response["output_text"] = (
                    f"```json\n{json.dumps(json_data, indent=2)}\n```"
                )
            except (ValueError, json.JSONDecodeError) as e:
                logger.error(f"Error processing JSON response: {str(e)}")

        return response

    def extract_json_from_text(self, text):
        """Extract JSON data from text output."""
        json_match = re.search(r"```json\n({.*?})\n```", text, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON content found in the text.")

        json_str = json_match.group(1)
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            data = {}

        return data

    def create_basic_document_structure(self, file_path, pdf_data):
        """Create a basic document structure when JSON extraction fails."""
        doc = fitz.open(file_path)

        # Extract basic metadata
        title = os.path.basename(file_path)
        content = "\n".join([page.get_text() for page in pdf_data])

        # Try to extract title from first page
        first_page_text = doc[0].get_text()
        title_match = re.search(r"^(.+?)\n", first_page_text)
        if title_match:
            title = title_match.group(1).strip()

        return {
            "title": title,
            "source_file": file_path,
            "content": content,
            "page_count": len(doc),
            "processed_date": datetime.datetime.now().isoformat(),
        }
