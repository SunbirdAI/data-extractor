import time

import pandas as pd

from config import logger
from utils.zotero_manager import ZoteroManager
from utils.zotero_pdf_processory import (
    down_zotero_collection_item_attachment_pdfs,
    export_dataframe_to_csv,
    get_zotero_collection_item_by_name,
    get_zotero_collection_items,
    process_multiple_pdfs,
    stuff_summarise_document_bullets,
    update_summary_columns,
)


def chat_function(
    message: str, study_name: str, prompt_type: str, variable_list: list, cache=None
) -> pd.DataFrame:
    """
    Process a chat message and generate a response using Zotero and PDF processing.

    Args:
        message (str): The user's query message
        study_name (str): Name of the study to process
        prompt_type (str): Type of prompt to use
        variable_list (list): List of variables to extract
        cache (LRUCache, optional): Cache instance for storing credentials

    Returns:
        pd.DataFrame: Results DataFrame
    """
    df = pd.DataFrame()
    zotero_library_type = "user"

    # Get credentials from cache
    zotero_library_id = cache.get("zotero_library_id") if cache else None
    zotero_api_access_key = cache.get("zotero_api_access_key") if cache else None

    if not zotero_library_id or not zotero_api_access_key:
        return pd.DataFrame(
            {
                "Error": [
                    "Zotero credentials not found. Please process your Zotero library first."
                ]
            }
        )

    logger.info(f"Starting process processing of {study_name}.")

    try:
        zotero_manager = ZoteroManager(
            zotero_library_id, zotero_library_type, zotero_api_access_key
        )

        start_time = time.time()

        # Get collection and items
        zotero_collection = get_zotero_collection_item_by_name(
            zotero_manager, study_name
        )
        collection_items = get_zotero_collection_items(
            zotero_manager, zotero_collection.key
        )
        attachments = down_zotero_collection_item_attachment_pdfs(
            zotero_manager, collection_items
        )

        if not attachments:
            return pd.DataFrame(
                {"Error": ["No PDF attachments found in the collection"]}
            )

        # Process PDFs
        variables = ", ".join(variable_list)
        df = process_multiple_pdfs(
            attachments, variables, stuff_summarise_document_bullets
        )

        df = update_summary_columns(df)

        # Export results
        msg = export_dataframe_to_csv(df, f"zotero_data/{study_name}.csv")
        logger.info(msg)

        # Log processing time
        end_time = time.time()
        elapsed_time = end_time - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)

        logger.info(
            f"Elapsed time to download and process {study_name} {len(attachments)} documents: {minutes} minutes and {seconds} seconds"
        )

        return df

    except Exception as e:
        logger.error(f"Error in chat_function: {str(e)}")
        return pd.DataFrame({"Error": [str(e)]})
