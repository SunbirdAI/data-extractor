# utils/zotero_pdf_processor.py
import json
import logging
import os
import re
import traceback
from typing import List, Optional

import pandas as pd
import requests
import tiktoken
from langchain import PromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from openai import OpenAI
from pyzotero.zotero_errors import HTTPError
from slugify import slugify

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def num_tokens_from_string(string: str, encoding_name: str = "gpt-4o-mini") -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.encoding_for_model(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens


def print_embedding_cost(texts):

    enc = tiktoken.encoding_for_model("text-embedding-3-small")
    total_tokens = sum([len(enc.encode(page.page_content)) for page in texts])
    print(f"Total Tokens: {total_tokens}")
    print(f"Embedding Cost in USD: {total_tokens / 1000 * 0.00002:.6f}")


# loading PDF, DOCX and TXT files as LangChain Documents
def load_document(file: str) -> Optional[List]:
    docs = []
    try:
        loaders = {".pdf": PyPDFLoader, ".docx": Docx2txtLoader, ".txt": TextLoader}

        extension = os.path.splitext(file)[1].lower()

        if extension not in loaders:
            raise ValueError(f"Unsupported document format: {extension}")

        print(f"Loading {file}")
        loader = loaders[extension](file)
        docs = loader.load()
    except Exception as e:
        logger.error(str(e))
        docs = []

    return docs


def extract_variables(text: str, variables: str, model="gpt-4o-mini"):
    """
    Extracts specified variables from the given text using OpenAI's GPT model.

    Args:
        text (str): The input text from which variables should be extracted.
        variables (str): A comma-separated string of variable names to extract.
        model (str): The OpenAI model to use (default is gpt-4).

    Returns:
        str: A JSON string containing only the extracted variables.
    """

    prompt = f"""
    Extract the following variables from the given text and return them in JSON format:
    Variables: {variables}

    Text:
    {text}

    Important:
    - The JSON output should contain only the extracted variables.
    - No extra text, comments, or formatting outside the JSON.
    - Do not ```json ``` code fences around the returned json data.
    - Do not return variable names if they are not found in the text.
    """

    client = OpenAI()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are an expert in structured data extraction.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    # Extract JSON output from the response
    extracted_data = response.choices[0].message.content.strip()

    try:
        # Ensure valid JSON
        json.loads(extracted_data)
        return extracted_data
    except json.JSONDecodeError:
        return "{}"  # Return an empty JSON if parsing fails


def extract_json_from_text(text):
    """
    Extracts JSON data embedded in a text string using regular expressions and converts it to a Python dictionary.

    Args:
        text (str): The text containing JSON data.

    Returns:
        dict: A dictionary representation of the JSON data.
    """
    try:
        data = json.loads(text)
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
        if not pdf_data:
            continue

        # Split the PDF data into chunks
        pdf_chunks = chunk_data(
            pdf_data, chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )

        # Summarize the document data
        output_summary = summarization_function(pdf_chunks, variables)
        # logger.info(f"Summary text: {output_summary_json}")

        # Extract JSON data from the summary text
        json_text = extract_variables(output_summary, variables)
        json_data = extract_json_from_text(json_text)

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


def stuff_summarise_document_bullets(docs, variables):
    system_prompt = """
    You are an expert research document summarizer. Your goal is to read and summarize 
    the content of the provided text in a structured, bullet-point format 
    focusing on the user’s specified study variables. After covering the main points, 
    include a concluding statement if relevant.
    
    Guidelines:
    • Present key findings or details as bullet points.
    • Address each study variable the user provides, where possible.
    • End with a concise conclusion or takeaway message.
    • Do not produce JSON.
    • Provide a readable, comprehensive summary in plain text.
    """
    user_prompt = """
    Below is the text we need to summarize:
    
    {context}
    
    The user wants a comprehensive, bullet-point summary focusing on 
    these study variables: {variables}
    
    - If a variable is not mentioned, you can either omit it or indicate 
      that it was not discussed.
    - Feel free to include any relevant details even if they do not fit 
      strictly under a single variable.
    - End with a concise conclusion or final takeaway.
    """
    human_message_template = PromptTemplate(
        template=user_prompt, input_variables=["context", "variables"]
    )

    prompt = ChatPromptTemplate.from_messages(
        [("system", system_prompt), ("human", human_message_template.template)]
    )

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    # Instantiate chain
    chain = create_stuff_documents_chain(llm, prompt)

    # Invoke chain
    result = chain.invoke({"context": docs, "variables": variables})
    return result


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
    for collection_item in zotero_collection_items:
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
