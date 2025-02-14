import json
import logging
import os
import shutil
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from gradio_client import Client
from pydantic import BaseModel, ConfigDict, constr

from docs import description, tags_metadata
from utils.zotero_pdf_processory import (
    export_dataframe_to_csv,
    process_multiple_pdfs,
    stuff_summarise_document_bullets,
    update_summary_columns,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GRADIO_URL = os.getenv("GRADIO_URL", "http://localhost:7860/")
logger.info(f"GRADIO_URL: {GRADIO_URL}")
client = Client(GRADIO_URL)

UPLOAD_DIR = "zotero_data/uploads"

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(
    title="ACRES RAG API",
    description=description,
    openapi_tags=tags_metadata,
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class StudyVariables(str, Enum):
    ebola_virus = "Ebola Virus"
    vaccine_coverage = "Vaccine coverage"
    genexpert = "GeneXpert"


class PromptType(str, Enum):
    default = "Default"
    highlight = "Highlight"
    evidence_based = "Evidence-based"


class StudyVariableRequest(BaseModel):
    study_variable: Union[StudyVariables, str]
    prompt_type: PromptType
    text: constr(min_length=1, strip_whitespace=True)  # type: ignore

    model_config = ConfigDict(from_attributes=True)


class DownloadCSV(BaseModel):
    headers: List[str]
    data: List[List[Any]]
    metadata: Optional[Any] = None  # Metadata is nullable

    model_config = ConfigDict(from_attributes=True)


class Study(BaseModel):
    study_name: constr(min_length=1, strip_whitespace=True)  # type: ignore

    model_config = ConfigDict(from_attributes=True)


class ZoteroCredentials(BaseModel):
    library_id: constr(min_length=1, strip_whitespace=True)  # type: ignore
    api_access_key: constr(min_length=1, strip_whitespace=True)  # type: ignore

    model_config = ConfigDict(from_attributes=True)


class UploadPdfFiles(BaseModel):
    study_variables: constr(min_length=1, strip_whitespace=True)  # type: ignore
    study_name: constr(min_length=1, strip_whitespace=True)  # type: ignore

    model_config = ConfigDict(from_attributes=True)


class DataFrameResponse(BaseModel):
    headers: List[str]
    data: List[List[Any]]
    metadata: Optional[Dict[str, Optional[List[Any]]]] = None


def format_dataframe(
    df: pd.DataFrame, include_metadata: bool = False
) -> Dict[str, Any]:
    """
    Convert DataFrame to specified format with optional metadata

    Args:
        df: Input DataFrame
        include_metadata: Whether to include metadata in the response

    Returns:
        Dictionary with headers, data, and optional metadata
    """
    # Convert headers
    headers = df.columns.tolist()

    # Convert data to nested list format
    data = df.values.tolist()

    # Create response
    response = {"headers": headers, "data": data, "metadata": None}

    # Add metadata if requested
    if include_metadata:
        metadata = {
            "dtypes": df.dtypes.astype(str).tolist(),
            "index": df.index.tolist(),
            "null_counts": df.isnull().sum().tolist(),
            "shape": list(df.shape),
        }
        response["metadata"] = metadata

    return response


def json_to_dataframe(json_data):
    """
    Converts a JSON object into a pandas DataFrame.

    Args:
        json_data (dict or str): The JSON object or JSON string to convert. Must include 'headers' and 'data' keys.

    Returns:
        pd.DataFrame: A pandas DataFrame created from the JSON data.
    """
    # If the input is a JSON string, parse it into a dictionary
    # Extract headers and data
    if isinstance(json_data, str):
        json_data = json.loads(json_data)
        headers = json_data.get("headers", [])
        data = json_data.get("data", [])
    else:
        headers = json_data.headers
        data = json_data.data

    # Convert to DataFrame
    dataframe = pd.DataFrame(data, columns=headers)

    return dataframe


@app.post("/process_zotero_library_items", tags=["zotero"])
def process_zotero_library_items(zotero_credentials: ZoteroCredentials):
    """Process items from a Zotero library using provided credentials.

    This endpoint integrates with Zotero to fetch and process library items. It uses the provided
    credentials to authenticate and access the specified Zotero library.

    Parameters
    ----------
    zotero_credentials : ZoteroCredentials
        Request body containing:
        - library_id (str): Zotero library identifier
        - api_access_key (str): Zotero API access key
        Both fields must be non-empty strings.

    Returns
    -------
    dict
        A dictionary containing the 'result' key with processed data from the Zotero library.
        The exact structure depends on the external client.predict() response.

    Raises
    ------
    HTTPException
        400 Bad Request - If required fields are missing or invalid
        500 Internal Server Error - If there is an issue calling client.predict or Zotero service fails

    Example
    -------
    Request body:
        {
            "library_id": "1234567",
            "api_access_key": "ZoteroApiKeyXYZ"
        }

    Response:
        {
            "result": {
                "someProcessedData": "..."
            }
        }

    Notes
    -----
    - Relies on external client.predict() to process Zotero library data
    - No file downloads or uploads in this endpoint
    - Ensure library_id and api_access_key are valid in the Zotero system
    """
    result = client.predict(
        zotero_library_id_param=zotero_credentials.library_id,
        zotero_api_access_key=zotero_credentials.api_access_key,
        api_name="/process_zotero_library_items",
    )
    return {"result": result}


@app.post("/get_study_info", tags=["zotero"])
def get_study_info(study: Study):
    """Retrieve detailed information about a specific study.

    This endpoint integrates with a remote service to get study details based on the provided study name.

    Parameters
    ----------
    study : Study
        Request body containing:
        - study_name (str): The name of the study to fetch info for
        Must be a non-empty string.

    Returns
    -------
    dict
        A dictionary containing the 'result' key with study details.
        The exact structure depends on the external client.predict() response.

    Raises
    ------
    HTTPException
        400 Bad Request - If study_name is missing or invalid
        500 Internal Server Error - If there is an issue with the external client.predict call

    Example
    -------
    Request body:
        {
            "study_name": "Global Ebola Research"
        }

    Response:
        {
            "result": {
                "studyDetails": "some details here"
                // additional data from external service
            }
        }

    Notes
    -----
    - Expects a valid study name that exists in the external system
    - Return data structure is dependent on client.predict response
    """
    result = client.predict(study_name=study.study_name, api_name="/get_study_info")
    return {"result": result}


@app.post("/study_variables", tags=["zotero"])
def process_study_variables(study_request: StudyVariableRequest):
    """Process text and return study variable data based on specified parameters.

    This endpoint uses an external service to interpret a textual prompt with a specified
    study variable and prompt type.

    Parameters
    ----------
    study_request : StudyVariableRequest
        Request body containing:
        - study_variable (StudyVariables | str): Either one of the enumerated values
          ('Ebola Virus', 'Vaccine coverage', 'GeneXpert') or a custom string
        - prompt_type (PromptType): One of 'Default', 'Highlight', or 'Evidence-based'
        - text (str): The text to process (must be non-empty) i.e "STUDYID, AUTHOR, YEAR, TITLE,
        PUBLICATION_TYPE, STUDY_DESIGN, STUDY_AREA_REGION, STUDY_POPULATION"

    Returns
    -------
    dict
        A dictionary containing the 'result' key with the first item of processed data.
        The exact structure depends on the external client.predict() response.

    Raises
    ------
    HTTPException
        400 Bad Request - If required fields are missing or invalid
        500 Internal Server Error - If there is an issue with the external service

    Example
    -------
    Request body:
        {
            "study_variable": "Ebola Virus",
            "prompt_type": "Default",
            "text": "Summarize the latest Ebola Virus research."
        }

    Response:
        {
            "result": "processed result from external service"
        }

    Notes
    -----
    - The study_variable field accepts both enumerated values and custom strings
    - prompt_type must be one of the predefined PromptType enum values
    - Returns only the first item from the result array (result[0])
    """
    result = client.predict(
        text=study_request.text,
        study_name=study_request.study_variable,
        prompt_type=study_request.prompt_type,
        api_name="/process_multi_input",
    )

    return {"result": result[0]}


@app.post("/new_study_choices", tags=["zotero"])
def new_study_choices():
    """Fetch a list of new study choices or suggestions.

    This endpoint retrieves a list of recommended or newly added study options from
    the external service. It does not require any input parameters.

    Parameters
    ----------
    None
        This endpoint does not accept any parameters.

    Returns
    -------
    dict
        A dictionary containing the 'result' key with an array of study choices.
        The exact structure depends on the external client.predict() response.

    Raises
    ------
    HTTPException
        500 Internal Server Error - If there is an issue with the external client.predict call

    Example
    -------
    Request:
        POST /new_study_choices

    Response:
        {
            "result": [
                // array of study choices from external service
            ]
        }

    Notes
    -----
    - Simple endpoint that delegates directly to client.predict
    - The external service logic determines the actual returned data structure
    """
    result = client.predict(api_name="/new_study_choices")
    return {"result": result}


@app.post("/download_csv", tags=["zotero"])
def download_csv(payload: DownloadCSV):
    """Generate and download a CSV file from provided data.

    This endpoint takes headers and data in a DataFrame-like structure and returns
    a downloadable CSV file. After generating the file, it triggers cleanup of temporary files.

    Parameters
    ----------
    payload : DownloadCSV
        Request body containing:
        - headers (List[str]): Column names for the CSV
        - data (List[List[Any]]): 2D array of data, each inner list is a row
        - metadata (Optional[Any]): Optional metadata about the data

    Returns
    -------
    FileResponse
        A downloadable CSV file with the following properties:
        - media_type: "text/csv"
        - filename: Generated from the server's file path

    Raises
    ------
    HTTPException
        404 Not Found - If the generated CSV file path is invalid or file not found
        400 Bad Request - If headers or data are malformed
        500 Internal Server Error - If saving, retrieving, or cleanup fails

    Example
    -------
    Request body:
        {
            "headers": ["Column1", "Column2", "Column3"],
            "data": [
                ["Value1", "Value2", "Value3"],
                ["Value4", "Value5", "Value6"]
            ],
            "metadata": {
                "description": "Sample data"
            }
        }

    Response:
        A downloadable CSV file containing the data

    Notes
    -----
    - Converts input data to CSV using client.predict
    - Automatically cleans up temporary files after download
    - Headers length should match the number of columns in each data row
    """
    json_data = payload.model_dump()
    result = client.predict(df=json_data, api_name="/download_as_csv")
    logger.info(result)

    file_path = result
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    clean_up = client.predict(api_name="/cleanup_temp_files")
    logger.info(clean_up)

    return FileResponse(
        file_path,
        media_type="text/csv",
        filename=os.path.basename(file_path),
    )


def save_upload_file(upload_file: UploadFile) -> str:
    """Save an uploaded file to disk with a timestamped filename.

    Parameters
    ----------
    upload_file : UploadFile
        The FastAPI UploadFile object containing the file to save

    Returns
    -------
    str
        The full path where the file was saved

    Notes
    -----
    - Creates UPLOAD_DIR if it doesn't exist
    - Generates filename using timestamp to prevent collisions
    - Filename format: YYYYMMDD_HHMMSS_original_filename
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{upload_file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)

    return file_path


@app.post("/upload_and_process_pdf_files", tags=["zotero"])
def handle_pdf_uploads(
    study_name: str = Form(),
    study_variables: str = Form(),
    files: List[UploadFile] = File(...),
):
    """Upload and process multiple PDF files for a given study.

    This endpoint accepts multiple PDF files along with study metadata, processes them
    to extract relevant study variables, and returns structured data. It also saves
    the processed data as a CSV file.

    Parameters
    ----------
    study_name : str
        Form field containing the name of the study to associate with these PDFs
    study_variables : str
        Form field containing the study variables to extract/analyze
    files : List[UploadFile]
        List of PDF files uploaded via multipart/form-data

    Returns
    -------
    dict
        A dictionary with 'data' key containing:
        - headers: List of column names
        - data: 2D array of processed data
        - metadata: Optional dictionary with DataFrame metadata
            - dtypes: Column data types
            - index: Row indices
            - null_counts: Null values per column
            - shape: DataFrame dimensions

    Raises
    ------
    HTTPException
        400 Bad Request - If required fields are missing or files are invalid
        500 Internal Server Error - If file processing or CSV export fails

    Example
    -------
    Request:
        Multipart form data with:
        - study_name: "EbolaStudy2025"
        - study_variables: "Ebola Virus, Transmission"
        - files: [file1.pdf, file2.pdf]

    Response:
        {
            "data": {
                "headers": ["Column1", "Column2"],
                "data": [["val1", "val2"], ["val3", "val4"]],
                "metadata": {
                    "dtypes": ["object", "object"],
                    "index": [0, 1],
                    "null_counts": [0, 0],
                    "shape": [2, 2]
                }
            }
        }

    Notes
    -----
    - Saves uploaded PDFs with timestamped filenames
    - Processes PDFs using stuff_summarise_document_bullets
    - Saves results to CSV in zotero_data/<study_name>.csv
    - Cleans up temporary files after processing
    """
    uploaded_files = [save_upload_file(file) for file in files]

    if uploaded_files:
        df = process_multiple_pdfs(
            uploaded_files, study_variables, stuff_summarise_document_bullets
        )

        df = update_summary_columns(df)
        msg = export_dataframe_to_csv(df, f"zotero_data/{study_name}.csv")
        logger.info(msg)
    else:
        df = pd.DataFrame(
            {"Attachments": ["Documents have no pdf attachements to process"]}
        )

    response = format_dataframe(df, include_metadata=True)

    client.predict(api_name="/cleanup_temp_files")

    return {"data": response}
