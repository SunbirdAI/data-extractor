description = """
Welcome to the Acres AI RAG API documentation.

### RAG Tasks
- Use the `/process_zotero_library_items`: Process zotero library items with your zotero credentials.
- Use the `/get_study_info`: Get number of documents in a zotero study.
- Use the `/study_variables`: Get research summary from the study provided the study variables.
- Use the `/download_csv`: Export the markdown text to a csv file.
- Use the `/upload_and_process_pdf_files`: Upload and process multiple PDF files for a given study.
This endpoint accepts multiple PDF files along with study metadata, processes them to extract relevant study variables, and returns structured data. It also saves the processed data as a CSV file.
"""

tags_metadata = [
    {"name": "ACRES RAG", "description": "AI RAG Application"},
]
