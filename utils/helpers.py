# utils/helpers.py

import json
from typing import Any, Dict, List

import chromadb
from chromadb.api.types import Document
from llama_index.core import Response

from rag.rag_pipeline import RAGPipeline
from utils.prompts import (
    StudyCharacteristics,
    VaccineCoverageVariables,
    structured_follow_up_prompt,
)

# Initialize ChromaDB client
chromadb_client = chromadb.Client()


def read_study_files(file_path):
    """
    Reads a JSON file and returns the parsed JSON data.

    Args:
        file_path (str): The path to the JSON file to be read.

    Returns:
        dict: The data from the JSON file as a Python dictionary.

    Raises:
        FileNotFoundError: If the file is not found at the provided path.
        json.JSONDecodeError: If the file contents are not valid JSON.

    Example:
        Given a JSON file 'study_files.json' with content like:
        {
            "Vaccine Coverage": "data/vaccine_coverage_zotero_items.json",
            "Ebola Virus": "data/ebola_virus_zotero_items.json",
            "Gene Xpert": "data/gene_xpert_zotero_items.json"
        }

        Calling `read_json_file("study_files.json")` will return:
        {
            "Vaccine Coverage": "data/vaccine_coverage_zotero_items.json",
            "Ebola Virus": "data/ebola_virus_zotero_items.json",
            "Gene Xpert": "data/gene_xpert_zotero_items.json"
        }
    """
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
        return data
    except FileNotFoundError as e:
        raise FileNotFoundError(f"The file at path {file_path} was not found.") from e
    except json.JSONDecodeError as e:
        raise ValueError(
            f"The file at path {file_path} does not contain valid JSON."
        ) from e


def append_to_study_files(file_path, new_key, new_value):
    """
    Appends a new key-value entry to an existing JSON file.

    Args:
        file_path (str): The path to the JSON file.
        new_key (str): The new key to add to the JSON file.
        new_value (any): The value associated with the new key (can be any valid JSON data type).

    Raises:
        FileNotFoundError: If the file is not found at the provided path.
        json.JSONDecodeError: If the file contents are not valid JSON.
        IOError: If the file cannot be written.

    Example:
        If the file 'study_files.json' initially contains:
        {
            "Vaccine Coverage": "data/vaccine_coverage_zotero_items.json",
            "Ebola Virus": "data/ebola_virus_zotero_items.json"
        }

        Calling `append_to_json_file("study_files.json", "Gene Xpert", "data/gene_xpert_zotero_items.json")`
        will modify the file to:
        {
            "Vaccine Coverage": "data/vaccine_coverage_zotero_items.json",
            "Ebola Virus": "data/ebola_virus_zotero_items.json",
            "Gene Xpert": "data/gene_xpert_zotero_items.json"
        }
    """
    try:
        # Read the existing data from the file
        with open(file_path, "r") as file:
            data = json.load(file)

        # Append the new key-value pair to the dictionary
        data[new_key] = new_value

        # Write the updated data back to the file
        with open(file_path, "w") as file:
            json.dump(data, file, indent=4)  # indent for pretty printing

    except FileNotFoundError as e:
        raise FileNotFoundError(f"The file at path {file_path} was not found.") from e
    except json.JSONDecodeError as e:
        raise ValueError(
            f"The file at path {file_path} does not contain valid JSON."
        ) from e
    except IOError as e:
        raise IOError(f"Failed to write to the file at {file_path}.") from e


def generate_follow_up_questions(
    rag: RAGPipeline, response: str, query: str, study_name: str
) -> List[str]:
    """
    Generates follow-up questions based on the given RAGPipeline, response, query, and study_name.
    Args:
        rag (RAGPipeline): The RAGPipeline object used for generating follow-up questions.
        response (str): The response to the initial query.
        query (str): The initial query.
        study_name (str): The name of the study.
    Returns:
        List[str]: A list of generated follow-up questions.
    Raises:
        None
    """

    # Determine the study type based on the study_name
    if "Vaccine Coverage" in study_name:
        study_type = "Vaccine Coverage"
        key_variables = list(VaccineCoverageVariables.__annotations__.keys())
    elif "Ebola Virus" in study_name:
        study_type = "Ebola Virus"
        key_variables = [
            "SAMPLE_SIZE",
            "PLASMA_TYPE",
            "DOSAGE",
            "FREQUENCY",
            "SIDE_EFFECTS",
            "VIRAL_LOAD_CHANGE",
            "SURVIVAL_RATE",
        ]
    elif "Gene Xpert" in study_name:
        study_type = "Gene Xpert"
        key_variables = [
            "OBJECTIVE",
            "OUTCOME_MEASURES",
            "SENSITIVITY",
            "SPECIFICITY",
            "COST_COMPARISON",
            "TURNAROUND_TIME",
        ]
    else:
        study_type = "General"
        key_variables = list(StudyCharacteristics.__annotations__.keys())

    # Add key variables to the context
    context = f"Study type: {study_type}\nKey variables to consider: {', '.join(key_variables)}\n\n{response}"

    follow_up_response = rag.query(
        structured_follow_up_prompt.format(
            context_str=context,
            query_str=query,
            response_str=response,
            study_type=study_type,
        )
    )

    questions = follow_up_response.response.strip().split("\n")
    cleaned_questions = []
    for q in questions:
        # Remove leading numbers and periods, and strip whitespace
        cleaned_q = q.split(". ", 1)[-1].strip()
        # Ensure the question ends with a question mark
        if cleaned_q and not cleaned_q.endswith("?"):
            cleaned_q += "?"
        if cleaned_q:
            cleaned_questions.append(f"✨ {cleaned_q}")
    return cleaned_questions[:3]


def add_study_files_to_chromadb(file_path: str, collection_name: str):
    """
    Reads the study files data from a JSON file and adds it to the specified ChromaDB collection.

    :param file_path: Path to the JSON file containing study files data.
    :param collection_name: Name of the ChromaDB collection to store the data.
    """
    # Load study files data from JSON file
    try:
        with open(file_path, "r") as f:
            study_files_data = json.load(f)
    except FileNotFoundError:
        print(f"File '{file_path}' not found.")
        return

    if not study_files_data:
        return

    # Get or create the collection in ChromaDB
    collection = chromadb_client.get_or_create_collection(collection_name)

    # Prepare lists for ids, texts, and metadata to batch insert
    ids = []
    documents = []
    metadatas = []

    # Populate lists with data from the JSON file
    for name, file_path in study_files_data.items():
        ids.append(name)  # Document ID
        documents.append("")  # Optional text, can be left empty if not used
        metadatas.append({"file_path": file_path})  # Metadata with file path

    # Add documents to the collection in batch
    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    print("All study files have been successfully added to ChromaDB.")


if __name__ == "__main__":
    # Usage example
    add_study_files_to_chromadb("study_files.json", "study_files_collection")
