# app.py
import os
import logging
from typing import Any, List, Tuple, Union

import gradio as gr
import openai
import pandas as pd
from cachetools import LRUCache
from dotenv import load_dotenv

from config import DATA_DIR, GRADIO_URL, OPENAI_API_KEY, logger
from interface.gradio_ui import demo
from utils.db import create_db_and_tables, get_study_files_by_library_id
from utils.helpers import (
    add_study_files_to_chromadb,
    create_directory,
)

create_directory(DATA_DIR)
# Configure logging
logging.basicConfig(level=logging.INFO)
logger.info(f"GRADIO_URL: {GRADIO_URL}")
load_dotenv()

environment = os.getenv("ENVIRONMENT", "development")

openai.api_key = OPENAI_API_KEY

# Initialize ChromaDB with study files
add_study_files_to_chromadb("study_files.json", "study_files_collection")

# Create sqlite study file data table
create_db_and_tables()


# Cache for RAG pipelines
rag_cache = {}

cache = LRUCache(maxsize=100)


def get_cache_value(key):
    return cache.get(key)


zotero_library_id = get_cache_value("zotero_library_id")
logger.info(f"zotero_library_id cache: {zotero_library_id}")


def refresh_study_choices():
    """
    Refresh study choices for a specific dropdown instance.

    :return: Updated Dropdown with current study choices
    """
    global study_choices, zotero_library_id
    zotero_library_id = get_cache_value("zotero_library_id")
    logger.info(f"zotero_library_id refreshed: {zotero_library_id}")
    study_choices = [
        file.name for file in get_study_files_by_library_id([zotero_library_id])
    ]
    logger.info(f"Study choices refreshed: {study_choices}")
    return study_choices


def new_study_choices():
    """
    Refresh study choices for a specific dropdown instance.
    """
    study_choices = refresh_study_choices()
    study_choices = ", ".join(study_choices)
    return f"**Your studies are: {study_choices}**"


if __name__ == "__main__":
    if environment == "development":
        logger.info("Running in development mode")
        demo.launch(share=True, debug=True)
    elif environment == "production":
        logger.info("Running in production mode")
        demo.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
            debug=False,
        )
