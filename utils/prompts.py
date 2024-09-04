from llama_index.core import PromptTemplate

highlight_prompt = PromptTemplate(
    "Context information is below.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Given this information, please answer the question: {query_str}\n"
    "Include all relevant information from the provided context. "
    "Highlight key information by enclosing it in **asterisks**. "
    "When quoting specific information, please use square brackets to indicate the source, e.g. [1], [2], etc."
)

evidence_based_prompt = PromptTemplate(
    "Context information is below.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Given this information, please answer the question: {query_str}\n"
    "Provide an answer to the question using evidence from the context above. "
    "Cite sources using square brackets."
)
