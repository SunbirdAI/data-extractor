import csv
import datetime
import io
import json
import os
import shutil
import time

import gradio as gr
import pandas as pd
from slugify import slugify

from config import DATA_DIR, UPLOAD_DIR, logger
from utils.db import (
    add_study_files_to_db,
    get_study_file_by_name,
    get_study_files_by_library_id,
)
from utils.helpers import add_study_files_to_chromadb, append_to_study_files
from utils.pdf_processor import PDFProcessor
from utils.zotero_pdf_processory import (
    export_dataframe_to_csv,
    process_multiple_pdfs,
    stuff_summarise_document_bullets,
    update_summary_columns,
)


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
        # Extract file paths from Gradio File objects
        file_paths = [file.name for file in files]

        # Store the original file paths for later reprocessing
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        collection_id = f"pdf_{slugify(name)}_{timestamp}"

        # Create a metadata file that stores original file paths and variables
        metadata = {
            "name": name,
            "timestamp": timestamp,
            "file_paths": file_paths,
            "initial_variables": variables,
        }

        os.makedirs(DATA_DIR, exist_ok=True)
        metadata_path = f"{DATA_DIR}/{collection_id}_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Process PDFs with variables if provided
        if variables:
            # Process PDFs using the same approach as Zotero
            df = process_multiple_pdfs(
                file_paths, variables, stuff_summarise_document_bullets
            )
            df.fillna("Not Available", inplace=True)

            # Update summary columns
            df = update_summary_columns(df)

            # Export to CSV
            os.makedirs("zotero_data", exist_ok=True)
            csv_output_path = f"zotero_data/{name}.csv"
            msg = export_dataframe_to_csv(df, csv_output_path)
            logger.info(msg)

            # Export the dataframe to JSON
            json_output_path = f"{DATA_DIR}/{collection_id}_data.json"
            with open(json_output_path, "w", encoding="utf-8") as f:
                json.dump(df.to_dict(orient="records"), f, indent=2, ensure_ascii=False)
        else:
            # If no variables specified, just create empty placeholder files
            json_output_path = metadata_path

        # Add to study files and ChromaDB
        append_to_study_files("study_files.json", collection_id, json_output_path)
        add_study_files_to_chromadb("study_files.json", "study_files_collection")
        add_study_files_to_db("study_files.json", "local")

        return (
            f"Successfully processed PDFs into collection: {collection_id}",
            collection_id,
        )
    except Exception as e:
        logger.error(f"Error in handle_pdf_upload: {str(e)}")
        return f"Error: {str(e)}", None


def process_pdf_query(variable_text: str, collection_id: str):
    """
    Process a PDF query with variables.

    Args:
        variable_text (str): Comma-separated list of variables to extract
        collection_id (str): The identifier of the PDF collection

    Returns:
        Tuple[pd.DataFrame, gr.update]: Query results and download button update
    """
    logger.info(f"Collection ID: {collection_id}")
    if not collection_id:
        return (
            pd.DataFrame(
                {"Error": ["No PDF collection uploaded. Please upload PDFs first."]}
            ),
            gr.update(visible=False),
        )

    # Find the study file by collection_id
    study = get_study_file_by_name(collection_id)
    logger.info(f"Study: {study}")
    if not study:
        return pd.DataFrame(
            {"Error": [f"Study for Collection '{collection_id}' not found."]}
        ), gr.update(visible=False)

    study_file_path = None
    # Try to find the data or metadata file
    for ext in ["_data.json", "_metadata.json"]:
        candidate = os.path.join(DATA_DIR, f"{collection_id}{ext}")
        if os.path.exists(candidate):
            study_file_path = candidate
            break

    if not study_file_path:
        return (
            pd.DataFrame({"Error": [f"Collection '{collection_id}' not found."]}),
            gr.update(visible=False),
        )

    try:
        start_time = time.time()
        # If this is a metadata file or no variables, reprocess PDFs
        is_metadata = study_file_path.endswith("_metadata.json")
        with open(study_file_path, "r") as f:
            metadata = json.load(f)

        file_paths = metadata.get("file_paths", [])
        if not file_paths:
            return pd.DataFrame({"Error": ["Original PDF files not found"]}), gr.update(
                visible=False
            )

        # Use provided variables or initial variables if none provided
        vars_to_use = (
            variable_text if variable_text else metadata.get("initial_variables", "")
        )
        if not vars_to_use:
            return (
                pd.DataFrame({"Error": ["Please specify variables to extract"]}),
                gr.update(visible=False),
            )

        # Reprocess the PDFs with the new variables
        logger.info(f"Reprocessing PDFs with variables: {vars_to_use}")
        df = process_multiple_pdfs(
            file_paths, vars_to_use, stuff_summarise_document_bullets
        )
        df.fillna("Not Available", inplace=True)
        df = update_summary_columns(df)

        # Export to CSV with updated variables
        name = metadata.get("name", collection_id)
        os.makedirs("zotero_data", exist_ok=True)
        csv_output_path = f"zotero_data/{name}_updated.csv"
        export_dataframe_to_csv(df, csv_output_path)

        # Update the data file
        data_path = study_file_path.replace("_metadata.json", "_data.json")
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(df.to_dict(orient="records"), f, indent=2, ensure_ascii=False)

        end_time = time.time()

        elapsed_time = end_time - start_time
        minutes = int(elapsed_time // 60)
        seconds = int(elapsed_time % 60)

        logger.info(
            f"Elapsed time to process {study.name} {len(file_paths)} pdf documents: {minutes} minutes and {seconds} seconds"
        )

        return df, gr.update(visible=True)
    except Exception as e:
        logger.error(f"Error processing PDF query: {str(e)}")
        return pd.DataFrame({"Error": [str(e)]}), gr.update(visible=False)


def download_as_csv(df):
    """
    Convert a DataFrame to CSV and provide the file path for download.

    Args:
        df (pd.DataFrame): The DataFrame to export.

    Returns:
        str: Path to the generated CSV file.
    """
    logger.info("Downloading as CSV")
    import datetime

    # Ensure the input is a DataFrame
    if not isinstance(df, pd.DataFrame):
        try:
            df = pd.DataFrame(df)
        except Exception as e:
            logger.error(f"Input could not be converted to DataFrame: {e}")
            return None

    # Create a unique temporary file path
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_path = os.path.join("zotero_data", f"study_export_{timestamp}.csv")

    try:
        # Export DataFrame to CSV
        df.to_csv(temp_path, index=False)
        logger.info(f"CSV exported to {temp_path}")
        return temp_path
    except Exception as e:
        logger.error(f"Error exporting DataFrame to CSV: {e}")
        return None


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
    """
    Clean up old temporary files (e.g., exported CSVs and uploads).
    """
    logger.info("Cleaning up temp files")
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

        # Clean up uploaded files in UPLOAD_DIR
        if os.path.exists(UPLOAD_DIR):
            for file in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, file)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                        logger.info(f"Removed upload file: {file}")
                except Exception as e:
                    logger.warning(f"Failed to remove upload file {file}: {e}")

        # Clean up downloaded files in zotero_data
        zotero_data_dir = "zotero_data"
        delete_files_in_directory(zotero_data_dir)

        return "Temporary files cleaned up."
    except Exception as e:
        logger.warning(f"Error during cleanup: {e}")
        return f"Error during cleanup: {e}"


def new_study_choices(zotero_library_id=None):
    """
    Refresh and return the list of available study choices as a Markdown string, a list, and a value.
    """
    logger.info("Refreshing study choices")
    logger.info(f"Zotero ID: {zotero_library_id}")
    try:
        if zotero_library_id:
            study_files = get_study_files_by_library_id([zotero_library_id])
        else:
            study_files = get_study_files_by_library_id([])

        study_choices = [file.name for file in study_files]
        # Markdown string
        if study_choices:
            md = f"**Your studies are:**<br>{'<br>'.join(study_choices)}"
            value = study_choices[0]
        else:
            md = "No studies found."
            value = None
        return md, gr.update(choices=study_choices, value=value)
    except Exception as e:
        logger.error(f"Error refreshing study choices: {e}")
        return "Error refreshing study choices.", gr.update(choices=[], value=None)


def markdown_table_to_csv(markdown_text: str) -> str:
    """
    Convert a markdown table to CSV format.

    Args:
        markdown_text (str): The markdown table text to convert

    Returns:
        str: CSV formatted string
    """
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
