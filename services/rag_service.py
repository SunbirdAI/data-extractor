import gradio as gr
import pandas as pd

from config import logger
from rag.rag_pipeline import RAGPipeline
from utils.db import get_study_file_by_name

from .chat_service import chat_function


def get_rag_pipeline(study_name: str, rag_cache: dict) -> RAGPipeline:
    """Get or create a RAGPipeline instance for the given study by querying ChromaDB."""
    if study_name not in rag_cache:
        study = get_study_file_by_name(study_name)

        if not study:
            raise ValueError(f"Invalid study name: {study_name}")

        study_file = study.file_path
        logger.info(f"study_file: {study_file}")
        if not study_file:
            raise ValueError(f"File path not found for study name: {study_name}")

        rag_cache[study_name] = RAGPipeline(study_file)

    return rag_cache[study_name]


def process_multi_input(variables: str, study_name: str, prompt_type: str, cache=None):
    """
    Process a study variable extraction request using either the RAG pipeline or chat function.

    Args:
        variables (str): Comma-separated list of variables to extract
        study_name (str): Name of the study to process
        prompt_type (str): Type of prompt to use
        cache (LRUCache, optional): Cache instance for storing credentials

    Returns:
        Tuple[pd.DataFrame, gr.update]: Results and Gradio update object
    """
    logger.info(
        f"Processing multi input: variables={variables}, study={study_name}, prompt={prompt_type}"
    )

    try:
        # Split variables into a list
        variable_list = [v.strip().upper() for v in variables.split(",")]
        user_message = f"Extract and present in a tabular format the following variables for each {study_name} study: {', '.join(variable_list)}"

        try:
            result_df = chat_function(
                user_message, study_name, prompt_type, variable_list, cache
            )
            if isinstance(result_df, pd.DataFrame) and not result_df.empty:
                return result_df, gr.update(visible=True)
            else:
                return pd.DataFrame({"Error": ["No data returned"]}), gr.update(
                    visible=True
                )
        except Exception as e:
            logger.warning(f"RAG summary pipeline failed: {e}")

    except Exception as e:
        logger.error(f"Error in process_multi_input: {e}")
        return pd.DataFrame({"Error": [str(e)]}), gr.update(visible=True)
