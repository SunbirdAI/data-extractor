# rag/rag_pipeline.py
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from dotenv import load_dotenv
from llama_index.core import Document, PromptTemplate, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter, SentenceWindowNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.chroma import ChromaVectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class RAGPipeline:
    def __init__(
        self,
        study_json,
        collection_name="study_files_rag_collection",
        use_semantic_splitter=False,
    ):
        self.study_json = study_json
        self.collection_name = collection_name
        self.use_semantic_splitter = use_semantic_splitter
        self.documents = None
        self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection(self.collection_name)
        self.embedding_model = OpenAIEmbedding(
            model_name="text-embedding-ada-002", api_key=os.getenv("OPENAI_API_KEY")
        )
        self.is_pdf = self._check_if_pdf_collection()
        self.load_documents()
        self.build_index()

    def _check_if_pdf_collection(self) -> bool:
        """Check if this is a PDF collection based on the JSON structure."""
        try:
            with open(self.study_json, "r") as f:
                data = json.load(f)
                # Check first document for PDF-specific fields
                if data and isinstance(data, list) and len(data) > 0:
                    return "pages" in data[0] and "source_file" in data[0]
            return False
        except Exception as e:
            logger.error(f"Error checking collection type: {str(e)}")
            return False

    def extract_page_number_from_query(self, query: str) -> int:
        """Extract page number from query text."""
        # Look for patterns like "page 3", "p3", "p. 3", etc.
        patterns = [
            r"page\s*(\d+)",
            r"p\.\s*(\d+)",
            r"p\s*(\d+)",
            r"pg\.\s*(\d+)",
            r"pg\s*(\d+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, query.lower())
            if match:
                return int(match.group(1))
        return None

    def load_documents(self):
        if self.documents is None:
            with open(self.study_json, "r") as f:
                self.data = json.load(f)

            self.documents = []
            if self.is_pdf:
                # Handle PDF documents
                for index, doc_data in enumerate(self.data):
                    pages = doc_data.get("pages", {})
                    for page_num, page_content in pages.items():
                        if isinstance(page_content, dict):
                            content = page_content.get("text", "")
                        else:
                            content = page_content

                        doc_content = (
                            f"Title: {doc_data['title']}\n"
                            f"Page {page_num} Content:\n{content}\n"
                            f"Authors: {', '.join(doc_data['authors'])}\n"
                        )

                        metadata = {
                            "title": doc_data.get("title"),
                            "authors": ", ".join(doc_data.get("authors", [])),
                            "year": doc_data.get("date"),
                            "source_file": doc_data.get("source_file"),
                            "page_number": int(page_num),
                            "total_pages": doc_data.get("page_count"),
                        }

                        self.documents.append(
                            Document(
                                text=doc_content,
                                id_=f"doc_{index}_page_{page_num}",
                                metadata=metadata,
                            )
                        )
            else:
                # Handle Zotero documents
                for index, doc_data in enumerate(self.data):
                    doc_content = (
                        f"Title: {doc_data.get('title', '')}\n"
                        f"Abstract: {doc_data.get('abstract', '')}\n"
                        f"Authors: {', '.join(doc_data.get('authors', []))}\n"
                        f"Fulltext: {doc_data.get('full_text', '')}\n"
                    )

                    metadata = {
                        "title": doc_data.get("title"),
                        "authors": ", ".join(doc_data.get("authors", [])),
                        "year": doc_data.get("date"),
                        "doi": doc_data.get("doi"),
                    }

                    self.documents.append(
                        Document(
                            text=doc_content, id_=f"doc_{index}", metadata=metadata
                        )
                    )

    def build_index(self):
        sentence_splitter = SentenceSplitter(chunk_size=2048, chunk_overlap=20)

        def _split(text: str) -> List[str]:
            return sentence_splitter.split_text(text)

        node_parser = SentenceWindowNodeParser.from_defaults(
            sentence_splitter=_split,
            window_size=5,
            window_metadata_key="window",
            original_text_metadata_key="original_text",
        )

        # Parse documents into nodes for embedding
        nodes = node_parser.get_nodes_from_documents(self.documents)

        # Initialize ChromaVectorStore with the existing collection
        vector_store = ChromaVectorStore(chroma_collection=self.collection)

        # Create the VectorStoreIndex using the ChromaVectorStore
        self.index = VectorStoreIndex(
            nodes, vector_store=vector_store, embed_model=self.embedding_model
        )

    def query(
        self, context: str, prompt_template: PromptTemplate = None
    ) -> Tuple[str, List[Any]]:
        if prompt_template is None:
            prompt_template = PromptTemplate(
                "Context information is below.\n"
                "---------------------\n"
                "{context_str}\n"
                "---------------------\n"
                "Given this information, please answer the question: {query_str}\n"
                "Follow these guidelines for your response:\n"
                "1. If the answer contains multiple pieces of information (e.g., author names, dates, statistics), "
                "present it in a markdown table format.\n"
                "2. For single piece information or simple answers, respond in a clear sentence.\n"
                "3. Always cite sources using square brackets for EVERY piece of information, e.g. [1], [2], etc.\n"
                "4. If the information spans multiple documents or pages, organize it by source.\n"
                "5. If you're unsure about something, say so rather than making assumptions.\n"
                "\nFormat tables like this:\n"
                "| Field | Information | Source |\n"
                "|-------|-------------|--------|\n"
                "| Title | Example Title | [1] |\n"
            )

        # Extract page number for PDF documents
        requested_page = (
            self.extract_page_number_from_query(context) if self.is_pdf else None
        )

        n_documents = len(self.index.docstore.docs)
        print(f"n_documents: {n_documents}")
        query_engine = self.index.as_query_engine(
            text_qa_template=prompt_template,
            similarity_top_k=n_documents if n_documents <= 17 else 15,
            response_mode="tree_summarize",
            llm=OpenAI(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY")),
        )

        response = query_engine.query(context)

        # Debug logging
        print(f"Response type: {type(response)}")
        print(f"Has source_nodes: {hasattr(response, 'source_nodes')}")
        if hasattr(response, "source_nodes"):
            print(f"Number of source nodes: {len(response.source_nodes)}")

        return response.response, getattr(response, "source_nodes", [])
