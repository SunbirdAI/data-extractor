import json
from typing import Any, Dict, List

from llama_index.core import Document, PromptTemplate, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter, SentenceWindowNodeParser
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI


class RAGPipeline:
    def __init__(self, study_json, use_semantic_splitter=False):
        self.study_json = study_json
        self.use_semantic_splitter = use_semantic_splitter
        self.documents = None
        self.index = None
        self.load_documents()
        self.build_index()

    def load_documents(self):
        if self.documents is None:
            with open(self.study_json, "r") as f:
                self.data = json.load(f)

            self.documents = []

            for index, doc_data in enumerate(self.data):
                doc_content = (
                    f"Title: {doc_data['title']}\n"
                    f"Abstract: {doc_data['abstract']}\n"
                    f"Authors: {', '.join(doc_data['authors'])}\n"
                    # f"full_text: {doc_data['full_text']}"
                )

                metadata = {
                    "title": doc_data.get("title"),
                    "authors": doc_data.get("authors", []),
                    "year": doc_data.get("date"),
                    "doi": doc_data.get("doi"),
                }

                self.documents.append(
                    Document(text=doc_content, id_=f"doc_{index}", metadata=metadata)
                )

    def build_index(self):
        if self.index is None:
            sentence_splitter = SentenceSplitter(chunk_size=2048, chunk_overlap=20)

            def _split(text: str) -> List[str]:
                return sentence_splitter.split_text(text)

            node_parser = SentenceWindowNodeParser.from_defaults(
                sentence_splitter=_split,
                window_size=5,
                window_metadata_key="window",
                original_text_metadata_key="original_text",
            )

            nodes = node_parser.get_nodes_from_documents(self.documents)
            self.index = VectorStoreIndex(
                nodes, embed_model=OpenAIEmbedding(model_name="text-embedding-3-large")
            )

    def query(
        self, context: str, prompt_template: PromptTemplate = None
    ) -> Dict[str, Any]:
        if prompt_template is None:
            prompt_template = PromptTemplate(
                "Context information is below.\n"
                "---------------------\n"
                "{context_str}\n"
                "---------------------\n"
                "Given this information, please answer the question: {query_str}\n"
                "Provide an answer to the question using evidence from the context above. "
                "Cite sources using square brackets for EVERY piece of information, e.g. [1], [2], etc. "
                "Even if there's only one source, still include the citation. "
                "If you're unsure about a source, use [?]. "
                "Ensure that EVERY statement from the context is properly cited."
            )

        # This is a hack to index all the documents in the store :)
        n_documents = len(self.index.docstore.docs)
        print(f"n_documents: {n_documents}")
        query_engine = self.index.as_query_engine(
            text_qa_template=prompt_template,
            similarity_top_k=n_documents if n_documents <= 17 else 15,
            response_mode="tree_summarize",
            llm=OpenAI(model="gpt-4o-mini"),
        )

        response = query_engine.query(context)

        return response
