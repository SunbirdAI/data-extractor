# app.py

import csv
import datetime
# from datetime import datetime
import io
import json
import logging
import os
from typing import Any, List, Tuple

import gradio as gr
import openai
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


def get_study_info(study_name: str | list) -> str:
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
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")


def chat_function(message: str, study_name: str, prompt_type: str) -> str:
    """Process a chat message and generate a response using the RAG pipeline."""

    if not message.strip():
        return "Please enter a valid query."

    rag = get_rag_pipeline(study_name)
    logger.info(f"rag: {rag}")
    prompt = {
        "Highlight": highlight_prompt,
        "Evidence-based": evidence_based_prompt,
    }.get(prompt_type)

    response, _ = rag.query(message, prompt_template=prompt)  # Unpack the tuple
    return response


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
    response = chat_function(user_message, study_name, prompt_type)
    return [response, gr.update(visible=True)]


def download_as_csv(markdown_content):
    """Convert markdown table to CSV and provide for download."""
    if not markdown_content:
        return None

    csv_content = markdown_table_to_csv(markdown_content)
    if not csv_content:
        return None

    # Create temporary file with actual content
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = f"study_export_{timestamp}.csv"

    with open(temp_path, "w", newline="", encoding="utf-8") as f:
        f.write(csv_content)

    return temp_path


# PDF Support
def process_pdf_uploads(files: List[gr.File], collection_name: str) -> str:
    """Process uploaded PDF files and add them to the system."""
    if not files or not collection_name:
        return "Please upload PDF files and provide a collection name"

    try:
        processor = PDFProcessor()

        # Save uploaded files temporarily
        file_paths = []
        for file in files:
            # Get the actual file path from the Gradio File object
            if hasattr(file, "name"):  # If it's already a path
                temp_path = file.name
            else:  # If it needs to be saved
                temp_path = os.path.join(processor.upload_dir, file.orig_name)
                file.save(temp_path)
            file_paths.append(temp_path)

        # Process PDFs
        output_path = processor.process_pdfs(file_paths, collection_name)

        # Add to study files and ChromaDB
        collection_id = f"pdf_{slugify(collection_name)}"
        append_to_study_files("study_files.json", collection_id, output_path)
        add_study_files_to_chromadb("study_files.json", "study_files_collection")

        # Cleanup temporary files if they were created by us
        for path in file_paths:
            if path.startswith(processor.upload_dir):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.warning(f"Failed to remove temporary file {path}: {e}")

        return f"Successfully processed PDFs into collection: {collection_id}"

    except Exception as e:
        logger.error(f"Error in process_pdf_uploads: {str(e)}")
        return f"Error processing PDF files: {str(e)}"


def chat_response(
    message: str,
    history: List[Tuple[str, str]],
    study_name: str,
    pdf_processor: PDFProcessor,
) -> Tuple[List[Tuple[str, str]], str, Any]:
    """Generate chat response and update history."""
    if not message.strip():
        return history, None, None

    rag = get_rag_pipeline(study_name)
    response, source_info = rag.query(message)
    history.append((message, response))

    # Generate PDF preview if source information is available
    preview_image = None
    if (
        source_info
        and source_info.get("source_file")
        and source_info.get("page_numbers")
    ):
        try:
            # Get the first page number from the source
            page_num = source_info["page_numbers"][0]
            preview_image = pdf_processor.render_page(
                source_info["source_file"], int(page_num)
            )
        except Exception as e:
            logger.error(f"Error generating PDF preview: {str(e)}")

    return history, preview_image


def create_gr_interface() -> gr.Blocks:
    """Create and configure the Gradio interface for the RAG platform."""
    global zotero_library_id

    with gr.Blocks(theme=gr.themes.Base()) as demo:
        gr.Markdown("# ACRES RAG Platform")

        with gr.Tabs() as tabs:
            # Tab 1: Original Study Analysis Interface
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

                        zotero_library_id = zotero_library_id_param.value
                        if zotero_library_id is None:
                            zotero_library_id = get_cache_value("zotero_library_id")
                        logger.info(f"zotero_library_id: =====> {zotero_library_id}")
                        study_choices = refresh_study_choices()
                        logger.info(f"study_choices_db: =====> {study_choices}")

                        study_dropdown = gr.Dropdown(
                            choices=study_choices,
                            label="Select Study",
                            value=(study_choices[0] if study_choices else None),
                            allow_custom_value=True,
                        )
                        # In Gradio interface setup
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
                            print("loading from local storage", saved_values)
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
                                placeholder="Type your variables separated by commas e.g (Study ID, Study Title, Authors etc)",
                                scale=4,
                                lines=1,
                                autofocus=True,
                            )
                            submit_btn = gr.Button("Submit", scale=1)
                        answer_output = gr.Markdown(label="Answer")
                        download_btn = gr.DownloadButton(
                            "Download as CSV",
                            variant="primary",
                            size="sm",
                            scale=1,
                            visible=False,
                        )

            # Tab 2: PDF Chat Interface
            with gr.Tab("PDF Chat"):
                pdf_processor = PDFProcessor()

                with gr.Row():
                    # Left column: Chat and Input
                    with gr.Column(scale=7):
                        chat_history = gr.Chatbot(
                            value=[], height=600, show_label=False
                        )
                        with gr.Row():
                            query_input = gr.Textbox(
                                show_label=False,
                                placeholder="Ask a question about your PDFs...",
                                scale=8,
                            )
                            chat_submit_btn = gr.Button(
                                "Send", scale=2, variant="primary"
                            )

                    # Right column: PDF Preview and Upload
                    with gr.Column(scale=3):
                        pdf_preview = gr.Image(label="Source Page", height=600)
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
                        current_collection = gr.State(value=None)

        # Event handlers for Study Analysis tab
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
            outputs=[new_studies],  # Update the same dropdown
        )

        # Event handlers for PDF Chat tab

        def handle_pdf_upload(files, name):
            if not name:
                return "Please provide a collection name", None
            if not files:
                return "Please select PDF files", None

            try:
                result = process_pdf_uploads(files, name)
                collection_id = f"pdf_{slugify(name)}"
                return result, collection_id
            except Exception as e:
                logger.error(f"Error in handle_pdf_upload: {str(e)}")
                return f"Error: {str(e)}", None

        upload_btn.click(
            handle_pdf_upload,
            inputs=[pdf_files, collection_name],
            outputs=[pdf_status, current_collection],
        )

        def add_message(history, message):
            """Add user message to chat history."""
            if not message.strip():
                raise gr.Error("Please enter a message")
            history = history + [(message, None)]
            return history, "", None

        def generate_chat_response(history, collection_id, pdf_processor):
            """Generate response for the last message in history."""
            if not collection_id:
                raise gr.Error("Please upload PDFs first")
            if len(history) == 0:
                return history, None

            last_message = history[-1][0]
            try:
                # Get response and source info
                rag = get_rag_pipeline(collection_id)
                response, source_info = rag.query(last_message)

                # Generate preview if source information is available
                preview_image = None
                if (
                    source_info
                    and source_info.get("source_file")
                    and source_info.get("page_number") is not None
                ):
                    try:
                        page_num = source_info["page_number"]
                        logger.info(f"Attempting to render page {page_num}")
                        preview_image = pdf_processor.render_page(
                            source_info["source_file"], page_num
                        )
                        if preview_image:
                            logger.info(
                                f"Successfully generated preview for page {page_num}"
                            )
                        else:
                            logger.warning(
                                f"Failed to generate preview for page {page_num}"
                            )
                    except Exception as e:
                        logger.error(f"Error generating PDF preview: {str(e)}")
                        preview_image = None

                # Update history with response
                history[-1] = (last_message, response)
                return history, preview_image

            except Exception as e:
                logger.error(f"Error in generate_chat_response: {str(e)}")
                history[-1] = (last_message, f"Error: {str(e)}")
                return history, None

        # Update PDF event handlers
        upload_btn.click(  # Change from pdf_files.upload to upload_btn.click
            handle_pdf_upload,
            inputs=[pdf_files, collection_name],
            outputs=[pdf_status, current_collection],
        )

        # Fixed chat event handling
        chat_submit_btn.click(
            add_message,
            inputs=[chat_history, query_input],
            outputs=[chat_history, query_input, pdf_preview],
        ).success(
            lambda h, c: generate_chat_response(h, c, pdf_processor),
            inputs=[chat_history, current_collection],
            outputs=[chat_history, pdf_preview],
        )

    return demo


demo = create_gr_interface()

if __name__ == "__main__":
    # demo = create_gr_interface()
    demo.launch(share=True, debug=True)
