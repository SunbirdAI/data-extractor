import json
import os

from cachetools import LRUCache
from slugify import slugify

from config import STUDY_FILES, logger
from utils.db import (
    add_study_files_to_db,
    get_study_file_by_name,
    get_study_files_by_library_id,
)
from utils.helpers import add_study_files_to_chromadb, append_to_study_files
from utils.zotero_manager import ZoteroManager


def process_zotero_library_items(
    zotero_library_id_param: str, zotero_api_access_key: str, cache: LRUCache
) -> str:
    global zotero_library_id
    if not zotero_library_id_param or not zotero_api_access_key:
        return "Please enter your zotero library Id and API Access Key"

    zotero_library_id = zotero_library_id_param
    cache["zotero_library_id"] = zotero_library_id
    zotero_library_type = "user"  # or "group"
    zotero_api_access_key = zotero_api_access_key
    cache["zotero_api_access_key"] = zotero_api_access_key

    message = ""

    try:
        zotero_manager = ZoteroManager(
            zotero_library_id, zotero_library_type, zotero_api_access_key
        )

        zotero_collections = zotero_manager.get_collections()
        zotero_collection_lists = zotero_manager.list_zotero_collections(
            zotero_collections
        )
        filtered_zotero_collection_lists = (
            zotero_manager.filter_and_return_collections_with_items(
                zotero_collection_lists
            )
        )

        study_files_data = {}  # Dictionary to collect items for ChromaDB

        for collection in filtered_zotero_collection_lists:
            collection_name = collection.get("name")
            if collection_name not in STUDY_FILES:
                collection_key = collection.get("key")
                collection_items = zotero_manager.get_collection_items(collection_key)
                zotero_collection_items = (
                    zotero_manager.get_collection_zotero_items_by_key(collection_key)
                )
                # Export zotero collection items to json
                zotero_items_json = zotero_manager.zotero_items_to_json(
                    zotero_collection_items
                )
                export_file = f"{slugify(collection_name)}_zotero_items.json"
                zotero_manager.write_zotero_items_to_json_file(
                    zotero_items_json, f"data/{export_file}"
                )
                logger.info(f"Adding {collection_name} - {export_file} to study files")
                append_to_study_files(
                    "study_files.json", collection_name, f"data/{export_file}"
                )

                # Collect for ChromaDB
                study_files_data[collection_name] = f"data/{export_file}"

                # Update in-memory STUDY_FILES for reference in current session
                STUDY_FILES.update({collection_name: f"data/{export_file}"})
                logger.info(f"STUDY_FILES: {STUDY_FILES}")

        # After loop, add all collected data to ChromaDB
        add_study_files_to_chromadb("study_files.json", "study_files_collection")
        # Add collected data to sqlite
        add_study_files_to_db("study_files.json", zotero_library_id)

        # Dynamically update study choices
        global study_choices
        study_choices = [
            file.name for file in get_study_files_by_library_id([zotero_library_id])
        ]
        message = "Successfully processed items in your zotero library"
    except Exception as e:
        message = f"Error process your zotero library: {str(e)}"

    return message


def get_study_info(study_name):
    """
    Retrieve information about the specified study.
    Returns a string summary (can be adapted to return a dict for more structure).
    """
    logger.info(f"Getting info for study: {study_name}")
    study = get_study_file_by_name(study_name)
    if not study:
        return "No study selected"

    study_file = study.file_path
    if not study_file or not os.path.exists(study_file):
        return f"Study file for '{study_name}' not found."

    try:
        with open(study_file, "r") as f:
            data = json.load(f)
        # If the file is a list of documents
        if isinstance(data, list):
            num_docs = len(data)
            return f"### Number of documents: {num_docs}"
        # If the file is a dict with a 'documents' key
        elif isinstance(data, dict):
            num_docs = len(data)
            return f"### Number of documents: {num_docs}"
        else:
            return f"Study '{study_name}' loaded, but format is unrecognized."
    except Exception as e:
        logger.error(f"Error reading study file: {e}")
        return f"Error reading study file for '{study_name}': {e}"
