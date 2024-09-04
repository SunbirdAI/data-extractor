import gradio as gr
import json
import os
from typing import Dict, Any
from llama_index.core import (
    SimpleDirectoryReader,
    VectorStoreIndex,
    Document,
    Response,
    PromptTemplate
)
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding

# Make sure to set your OpenAI API key in the Hugging Face Spaces secrets
import openai
openai.api_key = os.environ.get('OPENAI_API_KEY')



class RAGPipeline:
    def __init__(self, metadata_file, pdf_dir, use_semantic_splitter=False):
        self.metadata_file = metadata_file
        self.pdf_dir = pdf_dir
        self.index = None
        self.use_semantic_splitter = use_semantic_splitter
        self.load_documents()
        self.build_index()

    def load_documents(self):
        with open(self.metadata_file, 'r') as f:
            self.metadata = json.load(f)

        self.documents = []
        for item_key, item_data in self.metadata.items():
            metadata = item_data['metadata']
            pdf_path = item_data.get('pdf_path')

            if pdf_path:
                full_pdf_path = os.path.join(self.pdf_dir, os.path.basename(pdf_path))
                if os.path.exists(full_pdf_path):
                    pdf_content = SimpleDirectoryReader(input_files=[full_pdf_path]).load_data()[0].text
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

            self.documents.append(Document(
                text=doc_content,
                id_=item_key,
                metadata={
                    "title": metadata['title'],
                    "abstract": metadata['abstract'],
                    "authors": metadata['authors'],
                    "year": metadata['year'],
                    "doi": metadata['doi']
                }
            ))


    def build_index(self):
        if self.use_semantic_splitter:
            embed_model = OpenAIEmbedding()
            splitter = SemanticSplitterNodeParser(
                buffer_size=1,
                breakpoint_percentile_threshold=95,
                embed_model=embed_model
            )
        else:
            splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=20)

        nodes = splitter.get_nodes_from_documents(self.documents)
        self.index = VectorStoreIndex(nodes)


    def query(self, question, prompt_template=None):
        if prompt_template is None:
            prompt_template = PromptTemplate(
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

        query_engine = self.index.as_query_engine(
            text_qa_template=prompt_template,
            similarity_top_k=5
        )
        response = query_engine.query(question)

        return response