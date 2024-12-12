import logging
import os
from enum import Enum
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from gradio_client import Client
from pydantic import BaseModel, ConfigDict, Field, constr

from docs import description, tags_metadata

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GRADIO_URL = os.getenv("GRADIO_URL", "http://localhost:7860/")
logger.info(f"GRADIO_URL: {GRADIO_URL}")
client = Client(GRADIO_URL)

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
    study_variable: StudyVariables
    prompt_type: PromptType
    text: constr(min_length=1, strip_whitespace=True)  # type: ignore

    model_config = ConfigDict(from_attributes=True)


class DownloadCSV(BaseModel):
    text: constr(min_length=1, strip_whitespace=True)  # type: ignore

    model_config = ConfigDict(from_attributes=True)


class Study(BaseModel):
    study_name: constr(min_length=1, strip_whitespace=True)  # type: ignore

    model_config = ConfigDict(from_attributes=True)


class ZoteroCredentials(BaseModel):
    library_id: constr(min_length=1, strip_whitespace=True)  # type: ignore
    api_access_key: constr(min_length=1, strip_whitespace=True)  # type: ignore

    model_config = ConfigDict(from_attributes=True)


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
def download_csv(download_request: DownloadCSV):
    result = client.predict(
        markdown_content=download_request.text, api_name="/download_as_csv"
    )
    print(result)

    file_path = result
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Use FileResponse to send the file to the client
    return FileResponse(
        file_path,
        media_type="text/csv",  # Specify the correct MIME type for CSV
        filename=os.path.basename(
            file_path
        ),  # Provide a default filename for the download
    )
