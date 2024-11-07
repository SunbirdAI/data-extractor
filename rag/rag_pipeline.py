# rag/rag_pipeline.py
import json
import logging
from typing import Dict, Any, List

from llama_index.core import Document, VectorStoreIndex
from llama_index.core.node_parser import SentenceWindowNodeParser, SentenceSplitter
from llama_index.core import PromptTemplate
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.chroma import ChromaVectorStore
import chromadb
from typing import Dict, Any, List, Tuple
import re
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        self.embedding_model = OpenAIEmbedding(model_name="text-embedding-ada-002")
        self.load_documents()
        self.build_index()

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
            for index, doc_data in enumerate(self.data):
                # Process each page's content separately
                pages = doc_data.get("pages", {})
                for page_num, page_content in pages.items():
                    doc_content = (
                        f"Title: {doc_data['title']}\n"
                        f"Page {page_num} Content:\n{page_content}\n"
                        f"Authors: {', '.join(doc_data['authors'])}\n"
                    )

                    metadata = {
                        "title": doc_data.get("title"),
                        "authors": ", ".join(doc_data.get("authors", [])),
                        "year": doc_data.get("date"),
                        "doi": doc_data.get("doi"),
                        "source_file": doc_data.get("source_file"),
                        "page_number": int(page_num),  # Store as integer
                        "total_pages": len(pages),
                    }

                    self.documents.append(
                        Document(
                            text=doc_content,
                            id_=f"doc_{index}_page_{page_num}",
                            metadata=metadata,
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
    ) -> Tuple[str, Dict[str, Any]]:
        if prompt_template is None:
            prompt_template = PromptTemplate(
                "Context information is below.\n"
                "---------------------\n"
                "{context_str}\n"
                "---------------------\n"
                "Given this information, please answer the question: {query_str}\n"
                "Provide a detailed answer using the content from the context above. "
                "If the question asks about specific page content, make sure to include that information. "
                "Cite sources using square brackets for EVERY piece of information, e.g. [1, p.3], [2, p.5], etc. "
                "If you're unsure about something, say so rather than making assumptions."
            )

        # Extract page number from query if present
        requested_page = self.extract_page_number_from_query(context)
        logger.info(f"Requested page number: {requested_page}")

        query_engine = self.index.as_query_engine(
            text_qa_template=prompt_template,
            similarity_top_k=5,
            response_mode="tree_summarize",
            llm=OpenAI(model="gpt-4o-mini"),
        )

        response = query_engine.query(context)

        # Extract source information from the response nodes
        source_info = {}
        if hasattr(response, "source_nodes") and response.source_nodes:
            source_node = response.source_nodes[0]
            metadata = source_node.metadata

            # Use requested page number if available, otherwise use the page from metadata
            page_number = (
                requested_page
                if requested_page is not None
                else metadata.get("page_number", 0)
            )

            source_info = {
                "source_file": metadata.get("source_file"),
                "page_number": page_number,
                "title": metadata.get("title"),
                "authors": metadata.get("authors"),
                "content": source_node.text,
            }
            logger.info(f"Source info page number: {page_number}")

        return response.response, source_info
