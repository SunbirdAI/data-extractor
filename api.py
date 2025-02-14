import json
import logging
import os
import shutil
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Union

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from gradio_client import Client, handle_file
from pydantic import BaseModel, ConfigDict, Field, constr

from docs import description, tags_metadata
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
    result = client.predict(
        zotero_library_id_param=zotero_credentials.library_id,
        zotero_api_access_key=zotero_credentials.api_access_key,
        api_name="/process_zotero_library_items",
    )
    return {"result": result}


@app.post("/get_study_info", tags=["zotero"])
def get_study_info(study: Study):
    result = client.predict(study_name=study.study_name, api_name="/get_study_info")
    # print(result)
    return {"result": result}


@app.post("/study_variables", tags=["zotero"])
def process_study_variables(
    study_request: StudyVariableRequest,
):
    result = client.predict(
        text=study_request.text,  # "study id, study title, study design, study summary",
        study_name=study_request.study_variable,  # "Ebola Virus",
        prompt_type=study_request.prompt_type,  # "Default",
        api_name="/process_multi_input",
    )
    print(type(result))
    return {"result": result[0]}


@app.post("/new_study_choices", tags=["zotero"])
def new_study_choices():
    result = client.predict(api_name="/new_study_choices")
    return {"result": result}


@app.post("/download_csv", tags=["zotero"])
def download_csv(payload: DownloadCSV):
    json_data = payload.model_dump()
    result = client.predict(df=json_data, api_name="/download_as_csv")
    logger.info(result)

    file_path = result
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    clean_up = client.predict(api_name="/cleanup_temp_files")
    logger.info(clean_up)

    # Use FileResponse to send the file to the client
    return FileResponse(
        file_path,
        media_type="text/csv",  # Specify the correct MIME type for CSV
        filename=os.path.basename(
            file_path
        ),  # Provide a default filename for the download
    )


def save_upload_file(upload_file: UploadFile) -> str:
    """Save an uploaded file to disk."""
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
    uploaded_files = [save_upload_file(file) for file in files]

    if uploaded_files:
        df = process_multiple_pdfs(
            uploaded_files, study_variables, stuff_summarise_document_bullets
        )

        df = update_summary_columns(df)
        msg = export_dataframe_to_csv(df, f"zotero_data/{study_name}.csv")
        logger.info(msg)
        # markdown_table = dataframe_to_markdown(df)
    else:
        df = pd.DataFrame(
            {"Attachments": ["Documents have no pdf attachements to process"]}
        )

    # result = client.predict(
    #     files=[handle_file(file) for file in uploaded_files],
    # 	name=study_name,
    # 	variables=study_variables,
    #     api_name="/handle_pdf_upload")

    clean_up = client.predict(api_name="/cleanup_temp_files")
    logger.info(clean_up)

    return {"result": df.to_dict(orient="records")}
