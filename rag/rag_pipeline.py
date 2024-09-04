import json
import os
from typing import Dict, Any
from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    Document,
    StorageContext,
    load_index_from_storage,
)
from llama_index.core.node_parser import SentenceSplitter, SemanticSplitterNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core import PromptTemplate


class RAGPipeline:
    def __init__(
        self, metadata_file: str, pdf_dir: str, use_semantic_splitter: bool = False
    ):
        self.metadata_file = metadata_file
        self.pdf_dir = pdf_dir
        self.use_semantic_splitter = use_semantic_splitter
        self.index = None
        self.load_documents()
        self.build_index()

    def load_documents(self):
        with open(self.metadata_file, "r") as f:
            self.metadata = json.load(f)

        self.documents = []
        for item_key, item_data in self.metadata.items():
            metadata = item_data["metadata"]
            pdf_path = item_data.get("pdf_path")

            if pdf_path:
                full_pdf_path = os.path.join(self.pdf_dir, os.path.basename(pdf_path))
                if os.path.exists(full_pdf_path):
                    pdf_content = (
                        SimpleDirectoryReader(input_files=[full_pdf_path])
                        .load_data()[0]
                        .text
                    )
                else:
                    pdf_content = "PDF file not found"
            else:
                pdf_content = "PDF path not available in metadata"

            doc_content = (
                f"Title: {metadata['title']}\n"
                f"Abstract: {metadata['abstract']}\n"
                f"Authors: {metadata['authors']}\n"
                f"Year: {metadata['year']}\n"
                f"DOI: {metadata['doi']}\n"
                f"Full Text: {pdf_content}"
            )

            self.documents.append(
                Document(text=doc_content, id_=item_key, metadata=metadata)
            )

    def build_index(self):
        if self.use_semantic_splitter:
            embed_model = OpenAIEmbedding()
            splitter = SemanticSplitterNodeParser(
                buffer_size=1,
                breakpoint_percentile_threshold=95,
                embed_model=embed_model,
            )
        else:
            splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=20)

        nodes = splitter.get_nodes_from_documents(self.documents)
        self.index = VectorStoreIndex(nodes)

    def query(self, question: str, prompt_type: str = "default") -> Dict[str, Any]:
        prompt_template = self._get_prompt_template(prompt_type)

        query_engine = self.index.as_query_engine(
            text_qa_template=prompt_template, similarity_top_k=5
        )
        response = query_engine.query(question)

        return response

    def _get_prompt_template(self, prompt_type: str) -> PromptTemplate:
        if prompt_type == "highlight":
            return PromptTemplate(
                "Context information is below.\n"
                "---------------------\n"
                "{context_str}\n"
                "---------------------\n"
                "Given this information, please answer the question: {query_str}\n"
                "Include all relevant information from the provided context. "
                "Highlight key information by enclosing it in **asterisks**. "
                "When quoting specific information, please use square brackets to indicate the source, e.g. [1], [2], etc."
            )
        elif prompt_type == "evidence_based":
            return PromptTemplate(
                "Context information is below.\n"
                "---------------------\n"
                "{context_str}\n"
                "---------------------\n"
                "Given this information, please answer the question: {query_str}\n"
                "Provide an answer to the question using evidence from the context above. "
                "Cite sources using square brackets."
            )
        else:
            return PromptTemplate(
                "Context information is below.\n"
                "---------------------\n"
                "{context_str}\n"
                "---------------------\n"
                "Given this information, please answer the question: {query_str}\n"
                "Include all relevant information from the provided context. "
                "If information comes from multiple sources, please mention all of them. "
                "If the information is not available in the context, please state that clearly. "
                "When quoting specific information, please use square brackets to indicate the source, e.g. [1], [2], etc."
            )
