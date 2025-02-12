# utils/zotero_pdf_processor.py
import json
import logging
import os
import re
import traceback

import pandas as pd
import requests
from langchain import PromptTemplate
from langchain.chains.summarize import load_summarize_chain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import Docx2txtLoader
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import ChatOpenAI
from pyzotero.zotero_errors import HTTPError
from slugify import slugify
import tiktoken
from typing import List, Optional


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def print_embedding_cost(texts):

    enc = tiktoken.encoding_for_model("text-embedding-3-small")
    total_tokens = sum([len(enc.encode(page.page_content)) for page in texts])
    print(f"Total Tokens: {total_tokens}")
    print(f"Embedding Cost in USD: {total_tokens / 1000 * 0.00002:.6f}")


# loading PDF, DOCX and TXT files as LangChain Documents
def load_document(file: str) -> Optional[List]:
    loaders = {".pdf": PyPDFLoader, ".docx": Docx2txtLoader, ".txt": TextLoader}

    extension = os.path.splitext(file)[1].lower()

    if extension not in loaders:
        raise ValueError(f"Unsupported document format: {extension}")

    print(f"Loading {file}")
    loader = loaders[extension](file)

    return loader.load()


def extract_json_from_text(text):
    """
    Extracts JSON data embedded in a text string using regular expressions and converts it to a Python dictionary.

    Args:
        text (str): The text containing JSON data.

    Returns:
        dict: A dictionary representation of the JSON data.
    """
    # Extract the JSON part using a regular expression
    json_match = re.search(r"```json\n({.*?})\n```", text, re.DOTALL)
    if not json_match:
        raise ValueError("No JSON content found in the text.")

    json_str = json_match.group(1)

    # Parse the JSON string into a Python dictionary
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        # raise ValueError(f"Invalid JSON content: {e}")
        data = {}

    return data


def json_to_dataframe(json_data):
    """
    Converts a dictionary into a pandas DataFrame.

    Args:
        json_data (dict): The JSON data as a dictionary.

    Returns:
        pd.DataFrame: A DataFrame representation of the JSON data.
    """
    if isinstance(json_data, dict):
        # Flatten nested dictionaries if any
        flat_data = {
            k: (v if not isinstance(v, dict) else json.dumps(v))
            for k, v in json_data.items()
        }
        df = pd.DataFrame([flat_data])
    else:
        df = pd.DataFrame(json_data)

    return df


def pretty_print_json(json_data):
    """
    Pretty prints a JSON dictionary.

    Args:
        json_data (dict): The JSON data as a dictionary.
    """
    print(json.dumps(json_data, indent=4))


def process_multiple_pdfs(
    file_paths, variables, summarization_function, chunk_size=10000, chunk_overlap=100
):
    """
    Processes multiple PDF files and returns a combined DataFrame of extracted information.

    Args:
        file_paths (list): A list of file paths to PDF files.
        variables (str): A comma-separated string of variables to extract and summarize from the PDF content.
        summarization_function (function): A function that takes PDF chunks and variables as input and returns summarized JSON data.
        chunk_size (int, optional): The size of each chunk for splitting the PDF content. Default is 10000.
        chunk_overlap (int, optional): The overlap size between chunks. Default is 100.

    Returns:
        pd.DataFrame: A combined DataFrame containing extracted and summarized data from all PDF files.
    """
    combined_data = []

    for file_path in file_paths:
        # Load the PDF document
        pdf_data = load_document(file_path)

        # Split the PDF data into chunks
        pdf_chunks = chunk_data(
            pdf_data, chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

        # Summarize the document data into JSON format
        output_summary_json = summarization_function(pdf_chunks, variables)
        # logger.info(f"Summary json: {output_summary_json['output_text']}")

        # Extract JSON data from the summary text
        json_data = extract_json_from_text(output_summary_json["output_text"])

        # Convert JSON data to DataFrame
        if json_data:
            df = json_to_dataframe(json_data)

            # Add a column to identify the source file
            # df["Source_File"] = file_path

            # Append the DataFrame to the combined data
            combined_data.append(df)

    # Combine all DataFrames into a single DataFrame
    combined_df = pd.concat(combined_data, ignore_index=True)

    return combined_df


def json_to_markdown(json_data, indent_level=0):
    """
    Converts a JSON object into a Markdown-formatted string.

    Args:
        json_data (dict): The JSON data to convert.
        indent_level (int): The current indentation level for nested structures. Default is 0.

    Returns:
        str: A Markdown-formatted string representation of the JSON data.
    """
    markdown = ""
    indent = "  " * indent_level  # Two spaces per indent level

    if isinstance(json_data, dict):
        for key, value in json_data.items():
            markdown += f"{indent}- **{key}:**\n"
            markdown += json_to_markdown(
                value, indent_level + 1
            )  # Recursively handle nested structures
    elif isinstance(json_data, list):
        for item in json_data:
            markdown += (
                f"{indent}- {json_to_markdown(item, indent_level + 1).strip()}\n"
            )
    else:
        # For primitive types, just append the value
        markdown += f"{indent}{json_data}\n"

    return markdown


def update_summary_columns(df):
    """
    Updates all columns in a DataFrame that contain the word 'summary' in their name
    by converting JSON data into Markdown text.

    Args:
        df (pd.DataFrame): The DataFrame containing the JSON data to be converted.

    Returns:
        pd.DataFrame: A new DataFrame with the updated columns.
    """

    def process_column_data(json_data):
        # Parse JSON string to dict if it's a string
        if isinstance(json_data, str):
            try:
                json_data = json.loads(json_data)
            except json.JSONDecodeError:
                # Return the original string if it's not valid JSON
                return json_data

        # Convert dict to Markdown if it's a valid dict
        if isinstance(json_data, dict):
            return json_to_markdown(json_data)

        # Return the original data if not a JSON string or dict
        return json_data

    # Identify columns with 'summary' in their name
    summary_columns = [col for col in df.columns if "summary" in col.lower()]

    # Apply the processing function to each matching column
    for column_name in summary_columns:
        df[column_name] = df[column_name].apply(process_column_data)

    return df


def export_dataframe_to_csv(df, file_path, index=False):
    """
    Exports a DataFrame to a CSV file.

    Args:
        df (pd.DataFrame): The DataFrame to export.
        file_path (str): The file path where the CSV will be saved.
        index (bool, optional): Whether to include the DataFrame index in the CSV file. Default is False.

    Returns:
        str: A success message indicating the file has been saved.
    """
    try:
        # Export the DataFrame to CSV
        df.to_csv(file_path, index=index)
        return f"DataFrame successfully exported to {file_path}."
    except Exception as e:
        # Handle exceptions and return error message
        return f"An error occurred while exporting the DataFrame: {e}"


def dataframe_to_markdown(df):
    """
    Converts a Pandas DataFrame to a Markdown table.

    Args:
        df (pd.DataFrame): The DataFrame to convert.

    Returns:
        str: A Markdown-formatted string representing the DataFrame as a table.
    """
    if df.empty:
        return "The DataFrame is empty."

    # Get the column headers
    headers = list(df.columns)

    # Generate the Markdown header row and separator row
    header_row = "| " + " | ".join(headers) + " |"
    separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"

    # Generate the data rows
    data_rows = ["| " + " | ".join(map(str, row)) + " |" for row in df.values]

    # Combine all rows into a Markdown table
    markdown_table = "\n".join([header_row, separator_row] + data_rows)
    return markdown_table


# splitting data in chunks
def chunk_data(data, chunk_size=256, chunk_overlap=20):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunks = text_splitter.split_documents(data)
    return chunks


def summarise_document_data(chunks):
    prompt_template = """Write a concise summary of the following extracting the key information:
    Text: `{text}`
    CONCISE SUMMARY:"""
    initial_prompt = PromptTemplate(template=prompt_template, input_variables=["text"])

    refine_template = """
        Your job is to produce a final summary.
        I have provided an existing summary up to a certain point: {existing_answer}.
        Please refine the existing summary with some more context below.
        ------------
        {text}
        ------------
        Start the final summary with an INTRODUCTION PARAGRAPH that gives an overview of the topic FOLLOWED
        by BULLET POINTS if possible AND end the summary with a CONCLUSION PHRASE.
        
    """
    refine_prompt = PromptTemplate(
        template=refine_template, input_variables=["existing_answer", "text"]
    )

    llm = ChatOpenAI(temperature=0, model_name="gpt-4o-mini")
    chain = load_summarize_chain(
        llm=llm,
        chain_type="refine",
        question_prompt=initial_prompt,
        refine_prompt=refine_prompt,
        return_intermediate_steps=False,
    )
    output_summary = chain.invoke(chunks)
    return output_summary


def refine_summarise_document_data_json(chunks, variables):
    """
    Summarizes document data based on the provided text chunks and variables.

    Args:
        chunks (list of str): The text content to summarize.
        variables (dict): The variables to base the summary on.

    Returns:
        str: The summary in JSON format according to the variables provided.
    """
    prompt_template = """Write a concise summary of the following extracting the key information:
    Text: `{text}`
    CONCISE SUMMARY:"""
    initial_prompt = PromptTemplate(template=prompt_template, input_variables=["text"])

    refine_template = f"""
        Your job is to produce a final summary text that covers the key points based on the provided variables.
        VARIABLES: {variables}.
    """
    refine_template += """
        I have provided an existing summary up to a certain point: {existing_answer}.
        Please refine the existing summary with some more context below.
        ------------
        {text}
        ------------
        Break the summary according to the variables by BULLET POINTS if possible AND end the summary with a CONCLUSION PHRASE.
        Skip the References Section when generating the Summary.
        Return the summary in json format according to the variables given.
    """
    refine_prompt = PromptTemplate(
        template=refine_template, input_variables=["existing_answer", "text"]
    )

    llm = ChatOpenAI(temperature=0, model_name="gpt-4o-mini")
    chain = load_summarize_chain(
        llm,
        chain_type="refine",
        question_prompt=initial_prompt,
        refine_prompt=refine_prompt,
        return_intermediate_steps=False,
    )
    output_summary_json = chain.invoke(chunks)
    return output_summary_json


def map_reduce_summarise_document_data_json(chunks, variables):
    """
    Summarizes document data based on the provided text chunks and variables.

    Args:
        chunks (list of str): The text content to summarize.
        variables (dict): The variables to base the summary on.

    Returns:
        str: The summary in JSON format according to the variables provided.
    """
    map_prompt = """Write a concise summary of the following extracting the key information:
    Text: `{text}`
    CONCISE SUMMARY:"""
    map_prompt_template = PromptTemplate(template=map_prompt, input_variables=["text"])

    combine_prompt = f"""
        Your job is to produce a final summary text that covers the key points based on the provided variables.
        VARIABLES: {variables}.
    """
    combine_prompt += """
        Please refine the existing summary with some more context below.
        ------------
        {text}
        ------------
        Break the summary according to the variables by BULLET POINTS if possible AND end the summary with a CONCLUSION PHRASE.
        Skip the References Section when generating the Summary.
        Return the summary in json format according to the variables given.
    """
    combine_prompt_template = PromptTemplate(
        template=combine_prompt, input_variables=["text"]
    )

    llm = ChatOpenAI(temperature=0, model_name="gpt-4o-mini")
    chain = load_summarize_chain(
        llm,
        chain_type="map_reduce",
        map_prompt=map_prompt_template,
        combine_prompt=combine_prompt_template,
        verbose=False,
    )
    output_summary_json = chain.invoke(chunks)
    return output_summary_json


def stuff_summarise_document_data_json(chunks, variables):
    """
    Summarizes document data based on the provided text chunks and variables.

    Args:
        chunks (list of str): The text content to summarize.
        variables (dict): The variables to base the summary on.

    Returns:
        str: The summary in JSON format according to the variables provided.
    """
    prompt_template = """Write a detailed summary of the following extracting the key information:
    Text: `{text}`
    DETAILED SUMMARY:"""

    prompt_template += f"""
        Your job is to produce a final summary text that covers the key points based on the provided variables.
        VARIABLES: {variables}.
    """
    prompt_template += """
        Please refine the existing summary with some more context below.
        ------------
        {text}
        ------------
        Break the summary according to the variables by BULLET POINTS if possible AND end the summary with a CONCLUSION PHRASE.
        Skip the References Section when generating the Summary.
        Return the summary in json format according to the variables given.
    """
    prompt = PromptTemplate(template=prompt_template, input_variables=["text"])

    llm = ChatOpenAI(temperature=0, model_name="gpt-4o-mini")
    chain = load_summarize_chain(llm, chain_type="stuff", prompt=prompt, verbose=False)
    output_summary_json = chain.invoke(chunks)
    return output_summary_json


def extract_redirection_location_from_traceback(traceback_text):
    """
    Extracts the redirection location URL from a traceback error message.

    Args:
        traceback_text (str): The full traceback error message as a string.

    Returns:
        str: The extracted redirection location URL, or None if not found.
    """
    # Use a regular expression to find the redirection location URL
    location_pattern = r"Redirect location: '(.+?)'"
    match = re.search(location_pattern, traceback_text)
    if match:
        return match.group(1)  # Return the captured URL
    return None


def download_file_from_zotero(zotero_manager, key, directory, file_name):
    """
    Downloads a file from Zotero and saves it to the specified directory and file name.

    Args:
        zotero_manager: The Zotero manager instance to interact with the Zotero API.
        key: The Zotero item key for the file to download.
        directory: Directory where the file should be saved.
        file_name: The name of the file to save as.

    Returns:
        str: Full path to the saved file.
    """
    # Ensure the directory exists
    os.makedirs(directory, exist_ok=True)

    # Create the full file path
    file_path = os.path.join(directory, file_name)

    try:
        # Attempt to fetch the file directly
        file_content = zotero_manager.zot.file(key)
        if isinstance(file_content, bytes):  # If content is directly returned
            with open(file_path, "wb") as f:
                f.write(file_content)
        else:
            raise RuntimeError("Unexpected response when attempting to fetch the file.")

        return file_path

    except HTTPError as e:
        # Handle redirection errors
        tb_str = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        redirect_url = extract_redirection_location_from_traceback(tb_str)
        # print(f"redirect_url: {redirect_url}")
        if redirect_url:
            # Follow the redirection and download the file
            redirected_response = requests.get(redirect_url, stream=True)
            redirected_response.raise_for_status()
            with open(file_path, "wb") as f:
                for chunk in redirected_response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return file_path
        else:
            raise RuntimeError("Redirection occurred but no 'Location' header found.")

    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Failed to download the file: {e}")


def get_zotero_collection_item_by_name(zotero_manager, collection_name):
    zotero_collections = zotero_manager.get_collections()
    zotero_collection_lists = zotero_manager.list_zotero_collections(zotero_collections)
    collection = zotero_manager.find_zotero_collection_by_name(
        zotero_collection_lists, collection_name
    )
    return collection


def get_zotero_collection_items(zotero_manager, collection_key):
    zotero_collection_items = zotero_manager.get_collection_zotero_items_by_key(
        collection_key
    )
    return zotero_collection_items


def down_zotero_collection_item_attachment_pdfs(
    zotero_manager, zotero_collection_items
):
    file_paths = []
    for collection_item in zotero_collection_items[:10]:
        collection_item_children = zotero_manager.get_item_children(collection_item.key)
        if collection_item_children:
            key = collection_item_children[0]["key"]
            file_name = slugify(collection_item_children[0]["data"]["filename"])
            directory = "zotero_data"
            filename = f"{file_name}.pdf"
            file_path = download_file_from_zotero(
                zotero_manager, key, directory, filename
            )
            logger.info(f"File saved at: {file_path}")
            file_paths.append(file_path)

    return file_paths
