import json
import logging
import os
import shutil
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import pandas as pd
from cachetools import LRUCache
from dotenv import load_dotenv
from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from gradio_client import Client
from pydantic import BaseModel, ConfigDict, constr

from docs import description, tags_metadata
from services.file_service import cleanup_temp_files, download_as_csv
from services.file_service import new_study_choices as get_study_choices_service
from services.rag_service import process_multi_input
from services.zotero_service import get_study_info as get_study_info_service
from services.zotero_service import process_zotero_library_items
from utils.zotero_pdf_processory import (
    export_dataframe_to_csv,
    process_multiple_pdfs,
    stuff_summarise_document_bullets,
    update_summary_columns,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GRADIO_URL = os.getenv("GRADIO_URL", "http://localhost:7860/")
# logger.info(f"GRADIO_URL: {GRADIO_URL}")
# client = Client(GRADIO_URL)

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

router = APIRouter()

# Simple in-memory cache for demonstration
session_cache = {}

cache = LRUCache(maxsize=100)


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


class ZoteroLibraryRequest(BaseModel):
    zotero_library_id: str
    zotero_api_access_key: str


def get_session_data(session_token: Optional[str] = Cookie(default=None)):
    """
    Dependency to retrieve session data from the session cache.
    Raises HTTPException if session is missing or invalid.
    """
    if not session_token or session_token not in session_cache:
        raise HTTPException(
            status_code=401, detail="Session not found. Please authenticate."
        )
    return session_cache[session_token]


@router.post("/process_zotero_library_items", tags=["zotero"])
def process_zotero_library_items_endpoint(
    request: ZoteroLibraryRequest,
    response: Response,
    session_token: Optional[str] = Cookie(default=None),
):
    """
    Process the user's Zotero library and update study files and ChromaDB.

    This endpoint accepts Zotero credentials, processes the user's Zotero library,
    and stores the credentials in a session cookie for subsequent requests.

    Parameters
    ----------
    request : ZoteroLibraryRequest
        Request body containing:
        - zotero_library_id (str): The user's Zotero library ID
        - zotero_api_access_key (str): The user's Zotero API access key

    Returns
    -------
    dict
        A dictionary with:
        - message: Status message (success or error)
        - session_token: The session token to be used in subsequent requests (also set as a cookie)

    Raises
    ------
    HTTPException
        500 Internal Server Error - If processing fails

    Example
    -------
    Request body:
        {
            "zotero_library_id": "1234567",
            "zotero_api_access_key": "abcd1234efgh5678"
        }

    Response:
        {
            "message": "Successfully processed items in your zotero library",
            "session_token": "b1c2d3e4-5678-1234-9abc-abcdef123456"
        }

    Notes
    -----
    - The session_token is also set as a cookie for session management.
    - Use the session_token cookie in subsequent requests to access session-specific data.
    """
    try:
        # Use existing session token or create a new one
        if not session_token:
            session_token = str(uuid4())
            response.set_cookie(key="session_token", value=session_token, httponly=True)

        # Store credentials in the session cache
        session_cache[session_token] = {
            "zotero_library_id": request.zotero_library_id,
            "zotero_api_access_key": request.zotero_api_access_key,
        }

        # Call your service function directly
        message = process_zotero_library_items(
            request.zotero_library_id,
            request.zotero_api_access_key,
            cache=cache,  # You can pass session_cache[session_token] if your service supports it
        )
        return {"message": message, "session_token": session_token}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/get_study_info", tags=["zotero"])
def get_study_info(study: Study, session_data: dict = Depends(get_session_data)):
    """
    Retrieve detailed information about a specific study for the current session's Zotero library.

    This endpoint returns summary information about a study, such as the number of documents.

    Parameters
    ----------
    study : Study
        Request body containing:
        - study_name (str): The name of the study to fetch info for

    Returns
    -------
    dict
        A dictionary with:
        - result: A string summary of the study (e.g., number of documents)

    Raises
    ------
    HTTPException
        401 Unauthorized - If session or Zotero library ID is missing
        500 Internal Server Error - If there is an error fetching study info

    Example
    -------
    Request body:
        {
            "study_name": "Global Ebola Research"
        }

    Response:
        {
            "result": "### Number of documents: 42"
        }

    Notes
    -----
    - Requires a valid session (session_token cookie).
    - The study_name must exist in the user's Zotero library.
    """
    # Check for session and zotero_library_id
    if (
        not session_data
        or "zotero_library_id" not in session_data
        or not session_data["zotero_library_id"]
    ):
        raise HTTPException(
            status_code=401,
            detail="No Zotero session or library ID found. Please authenticate and process your Zotero library first.",
        )

    zotero_id = session_data["zotero_library_id"]
    study_name = study.study_name

    try:
        # Call your own service logic
        result = get_study_info_service(study_name)
        return {"result": result}
    except Exception as e:
        logger.error(f"Error in get_study_info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get study info: {e}")


@router.post("/study_variables", tags=["zotero"])
def process_study_variables(
    study_request: StudyVariableRequest, session_data: dict = Depends(get_session_data)
):
    """
    Process text and return study variable data based on specified parameters.

    This endpoint extracts variables from studies using the specified prompt type and returns the results as a table.

    Parameters
    ----------
    study_request : StudyVariableRequest
        Request body containing:
        - study_variable (str): The study name to process
        - prompt_type (str): The prompt type ("Default", "Highlight", "Evidence-based")
        - text (str): Comma-separated list of variables to extract (e.g., "STUDYID, AUTHOR, YEAR, TITLE")

    Returns
    -------
    dict
        A dictionary with:
        - result: An object containing headers (list of column names) and data (2D array of values)

    Raises
    ------
    HTTPException
        401 Unauthorized - If session or Zotero library ID is missing
        500 Internal Server Error - If processing fails

    Example
    -------
    Request body:
        {
            "study_variable": "Global Ebola Research",
            "prompt_type": "Default",
            "text": "STUDYID, AUTHOR, YEAR, TITLE"
        }

    Response:
        {
            "result": {
                "headers": ["STUDYID", "AUTHOR", "YEAR", "TITLE"],
                "data": [
                    ["123", "Smith", "2020", "Ebola Study"],
                    ["124", "Jones", "2021", "Vaccine Coverage"]
                ]
            }
        }

    Notes
    -----
    - Requires a valid session (session_token cookie).
    - The study_variable must exist in the user's Zotero library.
    """
    # Check for session and zotero_library_id
    if (
        not session_data
        or "zotero_library_id" not in session_data
        or not session_data["zotero_library_id"]
    ):
        raise HTTPException(
            status_code=401,
            detail="No Zotero session or library ID found. Please authenticate and process your Zotero library first.",
        )

    # Extract variables from request
    study_variable = study_request.study_variable
    prompt_type = study_request.prompt_type
    text = study_request.text

    try:
        # Call your own service logic
        result_df, _ = process_multi_input(text, study_variable, prompt_type, cache)

        # Replace problematic values
        result_df = result_df.replace([float("inf"), float("-inf")], None)
        result_df = result_df.where(
            pd.notnull(result_df), None
        )  # replaces NaN with None

        # Convert DataFrame to dict for JSON response
        result = {
            "headers": result_df.columns.tolist(),
            "data": result_df.values.tolist(),
        }
        return {"result": result}
    except Exception as e:
        logger.error(f"Error in process_study_variables: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to process study variables: {e}"
        )


@router.post("/new_study_choices", tags=["zotero"])
def new_study_choices_endpoint(session_data: dict = Depends(get_session_data)):
    """
    Fetch a list of available study choices for the current session's Zotero library.

    This endpoint returns a list of study names that the user can select from.

    Parameters
    ----------
    None
        Uses the session_token cookie to identify the user.

    Returns
    -------
    dict
        A dictionary with:
        - result: A list of study names (strings)

    Raises
    ------
    HTTPException
        401 Unauthorized - If session or Zotero library ID is missing

    Example
    -------
    Request:
        POST /new_study_choices

    Response:
        {
            "result": [
                "Global Ebola Research",
                "COVID-19 Vaccine Studies",
                "Malaria Interventions"
            ]
        }

    Notes
    -----
    - Requires a valid session (session_token cookie).
    - The returned list can be used to populate dropdowns or selection lists in the frontend.
    """
    # Check for session and zotero_library_id
    if (
        not session_data
        or "zotero_library_id" not in session_data
        or not session_data["zotero_library_id"]
    ):
        raise HTTPException(
            status_code=401,
            detail="No Zotero session or library ID found. Please authenticate and process your Zotero library first.",
        )

    zotero_id = session_data["zotero_library_id"]
    result = get_study_choices_service(zotero_id)
    return {"result": result}


@app.post("/download_csv", tags=["zotero"])
def download_csv(payload: DownloadCSV):
    """
    Generate a CSV file from provided data and return the file path.

    This endpoint takes tabular data (headers and rows), saves it as a CSV file on the server,
    and returns the file path. The client can then use this path to download the file via a separate endpoint.

    Parameters
    ----------
    payload : DownloadCSV
        Request body containing:
        - headers (List[str]): List of column names
        - data (List[List[Any]]): 2D array of data rows
        - metadata (Optional[Any]): Optional metadata about the data

    Returns
    -------
    dict
        A dictionary with:
        - file_path: The path to the generated CSV file on the server

    Raises
    ------
    HTTPException
        404 Not Found - If the file could not be created
        500 Internal Server Error - If there is an error during file creation

    Example
    -------
    Request body:
        {
            "headers": ["STUDYID", "AUTHOR", "YEAR", "TITLE"],
            "data": [
                ["123", "Smith", "2020", "Ebola Study"],
                ["124", "Jones", "2021", "Vaccine Coverage"]
            ],
            "metadata": null
        }

    Response:
        {
            "file_path": "zotero_data/study_export_20250503_220616.csv"
        }

    Notes
    -----
    - The client should use the returned file_path to download the file via a separate endpoint.
    - The file will be deleted after download or after a certain period for cleanup.
    """
    try:
        # Convert payload to DataFrame
        df = pd.DataFrame(payload.data, columns=payload.headers)
        # Replace problematic values for CSV export
        df = df.replace([float("inf"), float("-inf")], None)
        df = df.where(pd.notnull(df), None)

        # Use your own service to export DataFrame to CSV
        file_path = download_as_csv(df)
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        # Clean up temp files after download
        # cleanup_temp_files()

        return FileResponse(
            file_path,
            media_type="text/csv",
            filename=os.path.basename(file_path),
        )
    except Exception as e:
        logger.error(f"Error in download_csv: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate CSV: {e}")


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
        df.fillna("Not Available", inplace=True)
        logger.info(df)

        df = update_summary_columns(df)
        logger.info(df)
        msg = export_dataframe_to_csv(df, f"zotero_data/{study_name}.csv")
        logger.info(msg)
    else:
        df = pd.DataFrame(
            {"Attachments": ["Documents have no pdf attachements to process"]}
        )

    response = format_dataframe(df, include_metadata=True)

    cleanup_temp_files()

    return {"data": response}


app.include_router(router)
