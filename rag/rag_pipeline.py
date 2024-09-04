# rag/rag_pipeline.py

import json
from llama_index.core import Document, VectorStoreIndex
from llama_index.core.node_parser import SentenceWindowNodeParser, SentenceSplitter
from llama_index.core import PromptTemplate


class RAGPipeline:
    def __init__(self, study_json, use_semantic_splitter=False):
        self.study_json = study_json
        self.index = None
        self.use_semantic_splitter = use_semantic_splitter
        self.load_documents()
        self.build_index()

    def load_documents(self):
        with open(self.study_json, "r") as f:
            self.data = json.load(f)

        self.documents = []

        for index, doc_data in enumerate(self.data):
            doc_content = (
                f"Title: {doc_data['title']}\n"
                f"Authors: {', '.join(doc_data['authors'])}\n"
                f"Full Text: {doc_data['full_text']}"
            )

            metadata = {
                "title": doc_data.get("title"),
                "abstract": doc_data.get("abstract"),
                "authors": doc_data.get("authors", []),
                "year": doc_data.get("year"),
                "doi": doc_data.get("doi"),
            }

            self.documents.append(
                Document(text=doc_content, id_=f"doc_{index}", metadata=metadata)
            )

    def build_index(self):
        sentence_splitter = SentenceSplitter(chunk_size=128, chunk_overlap=13)

        def _split(text: str) -> List[str]:
            return sentence_splitter.split_text(text)

        node_parser = SentenceWindowNodeParser.from_defaults(
            sentence_splitter=_split,
            window_size=3,
            window_metadata_key="window",
            original_text_metadata_key="original_text",
        )

        nodes = node_parser.get_nodes_from_documents(self.documents)
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
            text_qa_template=prompt_template, similarity_top_k=5
        )
        response = query_engine.query(question)

        return response
