# app.py

import csv
import datetime
# from datetime import datetime
import io
import json
import logging
import os
import shutil
from typing import Any, List, Tuple, Union

import gradio as gr
import openai
import pandas as pd
from cachetools import LRUCache
from dotenv import load_dotenv
from slugify import slugify

from config import OPENAI_API_KEY, STUDY_FILES
from interface import create_chat_interface
from rag.rag_pipeline import RAGPipeline
from utils.db import (
    add_study_files_to_db,
    create_db_and_tables,
    get_all_study_files,
    get_study_file_by_name,
    get_study_files_by_library_id,
)
from utils.helpers import (
    add_study_files_to_chromadb,
    append_to_study_files,
    chromadb_client,
    create_directory,
)
from utils.pdf_processor import PDFProcessor
from utils.prompts import evidence_based_prompt, highlight_prompt
from utils.zotero_manager import ZoteroManager
from utils.zotero_pdf_processory import (
    dataframe_to_markdown,
    down_zotero_collection_item_attachment_pdfs,
    export_dataframe_to_csv,
    get_zotero_collection_item_by_name,
    get_zotero_collection_items,
    process_multiple_pdfs,
    stuff_summarise_document_bullets,
    stuff_summarise_document_data_json,
    update_summary_columns,
)

data_directory = "data"
create_directory(data_directory)
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

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


def get_rag_pipeline(study_name: str) -> RAGPipeline:
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


def get_study_info(study_name: Union[str, list]) -> str:
    """Retrieve information about the specified study."""
    if isinstance(study_name, list):
        study_name = study_name[0] if study_name else None

    if not study_name:
        return "No study selected"

    study = get_study_file_by_name(study_name)
    logger.info(f"Study: {study}")

    if not study:
        raise ValueError(f"Invalid study name: {study_name}")

    study_file = study.file_path
    logger.info(f"study_file: {study_file}")
    if not study_file:
        raise ValueError(f"File path not found for study name: {study_name}")

    with open(study_file, "r") as f:
        data = json.load(f)
    return f"### Number of documents: {len(data)}"


def markdown_table_to_csv(markdown_text: str) -> str:
    """Convert a markdown table to CSV format."""
    lines = [line.strip() for line in markdown_text.split("\n") if line.strip()]
    table_lines = [line for line in lines if line.startswith("|")]

    if not table_lines:
        return ""

    csv_data = []
    for line in table_lines:
        if "---" in line:
            continue
        # Split by |, remove empty strings, and strip whitespace
        cells = [cell.strip() for cell in line.split("|") if cell.strip()]
        csv_data.append(cells)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(csv_data)
    return output.getvalue()


def delete_files_in_directory(directory_path):
    """
    Deletes all files in the specified directory if it exists.

    Args:
        directory_path (str): Path to the directory whose files are to be deleted.

    Returns:
        str: Message indicating the result of the operation.
    """
    if not os.path.exists(directory_path):
        return f"Directory '{directory_path}' does not exist."

    if not os.path.isdir(directory_path):
        return f"'{directory_path}' is not a directory."

    try:
        # List all files and directories in the specified directory
        for item in os.listdir(directory_path):
            item_path = os.path.join(directory_path, item)
            # Check if it's a file and delete it
            if os.path.isfile(item_path):
                os.remove(item_path)
            # Check if it's a directory and delete it recursively
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        return f"All files and directories in '{directory_path}' have been deleted."
    except Exception as e:
        return f"An error occurred while deleting files: {e}"


def cleanup_temp_files():
    """Clean up old temporary files."""
    try:
        current_time = datetime.datetime.now()
        for file in os.listdir():
            if file.startswith("study_export_") and file.endswith(".csv"):
                file_time = datetime.datetime.fromtimestamp(os.path.getmtime(file))
                # Calculate the time difference in seconds
                time_difference = (current_time - file_time).total_seconds()
                if time_difference > 20:  # 5 minutes in seconds
                    try:
                        os.remove(file)
                    except Exception as e:
                        logger.warning(f"Failed to remove temp file {file}: {e}")
        logger.info("Cleaning up temporary files")
        delete_files_in_directory("zotero_data")
        delete_files_in_directory("zotero_data/uploads")
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")


def chat_function(
    message: str, study_name: str, prompt_type: str, variable_list: list
) -> str:
    """Process a chat message and generate a response using the RAG pipeline."""
    df = pd.DataFrame()
    zotero_library_type = "user"
    zotero_library_id = get_cache_value("zotero_library_id")
    zotero_api_access_key = get_cache_value("zotero_api_access_key")
    zotero_manager = ZoteroManager(
        zotero_library_id, zotero_library_type, zotero_api_access_key
    )

    if not message.strip():
        return "Please enter a valid query."

    zotero_collection = get_zotero_collection_item_by_name(zotero_manager, study_name)
    collection_items = get_zotero_collection_items(
        zotero_manager, zotero_collection.key
    )
    attachments = down_zotero_collection_item_attachment_pdfs(
        zotero_manager, collection_items
    )
    variables = ", ".join(variable_list)
    if attachments:
        df = process_multiple_pdfs(
            attachments, variables, stuff_summarise_document_bullets
        )

        df = update_summary_columns(df)
        msg = export_dataframe_to_csv(df, f"zotero_data/{study_name}.csv")
        logger.info(msg)
        # markdown_table = dataframe_to_markdown(df)
    else:
        df = pd.DataFrame(
            {"Attachments": ["Documents have no pdf attachements to process"]}
        )

    return df


def process_zotero_library_items(
    zotero_library_id_param: str, zotero_api_access_key: str
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


process_zotero_library_items(
    os.getenv("ZOTERO_LIBRARY_ID"), os.getenv("ZOTERO_API_ACCESS_KEY")
)


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


def process_multi_input(text, study_name, prompt_type):
    # Split input based on commas and strip any extra spaces
    variable_list = [word.strip().upper() for word in text.split(",")]
    user_message = f"Extract and present in a tabular format the following variables for each {study_name} study: {', '.join(variable_list)}"
    logger.info(f"User message: {user_message}")
    response = chat_function(user_message, study_name, prompt_type, variable_list)
    return [response, gr.update(visible=True)]


def download_as_csv(df):
    """Convert dataframe to CSV and provide for download."""

    # Create temporary file with actual content
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = f"zotero_data/study_export_{timestamp}.csv"

    export_dataframe_to_csv(df, temp_path)

    return temp_path


# ---------------------------
# PDF Upload and Query Functions
# ---------------------------


def handle_pdf_upload(files, name, variables=""):
    """
    Process the uploaded PDF files and add them to the system.

    Args:
        files (List[gr.File]): List of uploaded PDF files
        name (str): Name for the PDF collection
        variables (str): Optional comma-separated list of variables to extract

    Returns:
        Tuple[str, str]: Status message and collection ID
    """
    if not name:
        return "Please provide a collection name", None
    if not files:
        return "Please select PDF files", None

    try:
        # Initialize processor with larger chunk size for better context
        processor = PDFProcessor(chunk_size=4000, chunk_overlap=200)

        # Process PDFs with variables if provided
        output_path = processor.process_pdfs(files, name, variables)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        collection_id = f"pdf_{slugify(name)}_{timestamp}"

        # Add to study files and ChromaDB
        append_to_study_files("study_files.json", collection_id, output_path)
        add_study_files_to_chromadb("study_files.json", "study_files_collection")
        add_study_files_to_db("study_files.json", "local")

        return (
            f"Successfully processed PDFs into collection: {collection_id}",
            collection_id,
        )
    except Exception as e:
        logger.error(f"Error in handle_pdf_upload: {str(e)}")
        return f"Error: {str(e)}", None


def process_pdf_query(variable_text: str, collection_id: str) -> tuple:
    """
    Process a PDF query with variables.

    Args:
        variable_text (str): Comma-separated list of variables to extract
        collection_id (str): The identifier of the PDF collection

    Returns:
        Tuple[pd.DataFrame, any]: Query results and download button update
    """
    logger.info(f"Collection ID: {collection_id}")
    if not collection_id:
        return pd.DataFrame(
            {"Error": ["No PDF collection uploaded. Please upload PDFs first."]}
        ), gr.update(visible=False)

    study = get_study_file_by_name(collection_id)
    logger.info(f"Study: {study}")
    if not study:
        return pd.DataFrame(
            {"Error": [f"Collection '{collection_id}' not found."]}
        ), gr.update(visible=False)

    try:
        # Read the existing JSON file
        file_path = study.file_path
        logger.info(f"File Path: {file_path}")
        with open(file_path, "r") as f:
            data = json.load(f)
            # logger.info(f"Data: {data}")

        # If variables specified, filter the data
        if variable_text:
            variable_list = [v.strip().upper() for v in variable_text.split(",")]
            logger.info(f"Variable list: {variable_list}")
            filtered_data = []
            for doc in data:
                filtered_doc = {}
                for var in variable_list:
                    # Add the variable to filtered_doc even if it's not in the original
                    # This ensures all requested variables appear in the output
                    filtered_doc[var] = doc.get(var)
                filtered_data.append(filtered_doc)
            data = filtered_data
            # logger.info(f"Filtered Data: {filtered_data}")

        df = pd.DataFrame(data)
        return df, gr.update(visible=True)
    except Exception as e:
        logger.error(f"Error processing PDF query: {str(e)}")
        return pd.DataFrame({"Error": [str(e)]}), gr.update(visible=False)


# ---------------------------
# Main Gradio Interface Function
# ---------------------------


def create_gr_interface() -> gr.Blocks:
    """Create and configure the Gradio interface for the ACRES RAG Platform."""
    with gr.Blocks(theme=gr.themes.Base()) as demo:
        gr.Markdown("# ACRES RAG Platform")

        with gr.Tabs() as tabs:
            # ----- Tab 1: Study Analysis Interface -----
            with gr.Tab("Study Analysis"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Zotero Credentials")
                        zotero_library_id_param = gr.Textbox(
                            label="Zotero Library ID",
                            type="password",
                            placeholder="Enter Your Zotero Library ID here...",
                        )
                        zotero_api_access_key = gr.Textbox(
                            label="Zotero API Access Key",
                            type="password",
                            placeholder="Enter Your Zotero API Access Key...",
                        )
                        process_zotero_btn = gr.Button("Process your Zotero Library")
                        zotero_output = gr.Markdown(label="Zotero")

                        local_storage_state = gr.BrowserState(
                            {"zotero_library_id": "", "study_choices": []}
                        )

                        gr.Markdown("### Study Information")
                        study_choices = refresh_study_choices()
                        study_dropdown = gr.Dropdown(
                            choices=study_choices,
                            label="Select Study",
                            value=(study_choices[0] if study_choices else None),
                            allow_custom_value=True,
                        )
                        refresh_button = gr.Button("Refresh Studies")
                        study_info = gr.Markdown(label="Study Details")
                        new_studies = gr.Markdown(label="Your Studies")
                        prompt_type = gr.Radio(
                            ["Default", "Highlight", "Evidence-based"],
                            label="Prompt Type",
                            value="Default",
                        )

                        @demo.load(
                            inputs=[local_storage_state],
                            outputs=[zotero_library_id_param],
                        )
                        def load_from_local_storage(saved_values):
                            logger.info(f"Loading from local storage: {saved_values}")
                            return saved_values.get("zotero_library_id")

                        @gr.on(
                            [
                                zotero_library_id_param.change,
                                process_zotero_btn.click,
                                refresh_button.click,
                            ],
                            inputs=[zotero_library_id_param],
                            outputs=[local_storage_state],
                        )
                        def save_to_local_storage(zotero_library_id_param):
                            study_choices = refresh_study_choices()
                            return {
                                "zotero_library_id": zotero_library_id_param,
                                "study_choices": study_choices,
                            }

                    with gr.Column(scale=3):
                        gr.Markdown("### Study Variables")
                        with gr.Row():
                            study_variables = gr.Textbox(
                                show_label=False,
                                placeholder="Type your variables separated by commas e.g. (Study ID, Study Title, Authors etc)",
                                scale=4,
                                lines=1,
                                autofocus=True,
                            )
                            submit_btn = gr.Button("Submit", scale=1)
                        answer_output = gr.DataFrame(label="Answer")
                        download_btn = gr.DownloadButton(
                            "Download as CSV",
                            variant="primary",
                            size="sm",
                            scale=1,
                            visible=False,
                        )

            # ----- Tab 2: PDF Query Interface -----
            with gr.Tab("PDF Query"):
                with gr.Row():
                    # Left column: PDF query interface
                    with gr.Column(scale=7):
                        gr.Markdown("### PDF Query Variables")
                        pdf_variables = gr.Textbox(
                            show_label=False,
                            placeholder="Type your variables separated by commas (e.g., Title, Author, Date)",
                            scale=8,
                            lines=1,
                            autofocus=True,
                        )
                        pdf_submit_btn = gr.Button("Submit", scale=2)
                        pdf_answer_output = gr.DataFrame(label="Answer")
                        pdf_download_btn = gr.DownloadButton(
                            "Download as CSV",
                            variant="primary",
                            size="sm",
                            scale=1,
                            visible=False,
                        )
                    # Right column: PDF upload and processing
                    with gr.Column(scale=3):
                        upload_variables = gr.Textbox(
                            label="Initial Variables",
                            placeholder="Optional: Variables to extract during upload",
                            lines=1,
                        )
                        with gr.Row():
                            pdf_files = gr.File(
                                file_count="multiple",
                                file_types=[".pdf"],
                                label="Upload PDFs",
                            )
                        with gr.Row():
                            collection_name = gr.Textbox(
                                label="Collection Name",
                                placeholder="Name this PDF collection...",
                            )
                        with gr.Row():
                            upload_btn = gr.Button("Process PDFs", variant="primary")
                        pdf_status = gr.Markdown()
                        # State to hold the collection ID after upload.
                        current_collection = gr.State(value=None)

                # Event handler for processing PDF uploads.
                upload_btn.click(
                    handle_pdf_upload,
                    inputs=[pdf_files, collection_name, upload_variables],
                    outputs=[pdf_status, current_collection],
                )

                # Event handler for processing the PDF query.
                pdf_submit_btn.click(
                    process_pdf_query,
                    inputs=[pdf_variables, current_collection],
                    outputs=[pdf_answer_output, pdf_download_btn],
                )

                # Download button handler.
                pdf_download_btn.click(
                    fn=download_as_csv,
                    inputs=[pdf_answer_output],
                    outputs=[pdf_download_btn],
                ).then(fn=cleanup_temp_files, inputs=None, outputs=None)

        # ----- Event Handlers for the Study Analysis Tab -----
        process_zotero_btn.click(
            process_zotero_library_items,
            inputs=[zotero_library_id_param, zotero_api_access_key],
            outputs=[zotero_output],
        )

        study_dropdown.change(
            get_study_info, inputs=[study_dropdown], outputs=[study_info]
        )

        submit_btn.click(
            process_multi_input,
            inputs=[study_variables, study_dropdown, prompt_type],
            outputs=[answer_output, download_btn],
        )

        download_btn.click(
            fn=download_as_csv, inputs=[answer_output], outputs=[download_btn]
        ).then(fn=cleanup_temp_files, inputs=None, outputs=None)

        refresh_button.click(
            fn=new_study_choices,
            outputs=[new_studies],
        )

    return demo


demo = create_gr_interface()

if __name__ == "__main__":
    # demo = create_gr_interface()
    demo.launch(share=True, debug=True)
