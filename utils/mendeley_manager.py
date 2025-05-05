import json
import os

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth
from slugify import slugify

# Load environment variables from .env file
load_dotenv()


class MendeleyManager:
    def __init__(self, client_id=None, client_secret=None, redirect_uri=None):
        self.client_id = client_id or os.getenv("MENDELEY_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("MENDELEY_SECRET_KEY")
        self.redirect_uri = redirect_uri or os.getenv("MENDELEY_REDIRECT_URI")
        self.base_url = "https://api.mendeley.com"

        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise RuntimeError(
                "Missing MENDELEY_CLIENT_ID, MENDELEY_SECRET_KEY, or MENDELEY_REDIRECT_URI in environment variables"
            )

    def get_auth_url(self):
        """Generate the authorization URL."""
        scope = (
            "all"  # Replace "all" with the specific scopes you need # all, read, write
        )
        auth_url = f"{self.base_url}/oauth/authorize?client_id={self.client_id}&redirect_uri={self.redirect_uri}&response_type=code&scope={scope}"
        return auth_url

    def get_access_token(self, auth_code):
        """Exchange authorization code for an access token."""
        try:
            token_url = f"{self.base_url}/oauth/token"
            data = {
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": self.redirect_uri,
            }
            response = requests.post(
                token_url,
                data=data,
                auth=HTTPBasicAuth(self.client_id, self.client_secret),
            )
            response.raise_for_status()
            return response.json().get("access_token")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching access token: {e}")
            return None

    def list_documents(self, access_token):
        """List all documents."""
        try:
            url = f"{self.base_url}/documents"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error listing documents: {e}")
            return None

    def list_collections(self, access_token):
        """List all collections."""
        try:
            url = f"{self.base_url}/folders"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error listing collections: {e}")
            return None

    def check_document_exists(self, access_token, file_hash):
        """Check if a document exists for a given file hash."""
        try:
            url = f"{self.base_url}/catalog?filehash={file_hash}"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error checking document existence: {e}")
            return None

    def extract_metadata(self, access_token, pdf_file_path):
        """Extract metadata from a PDF file."""
        try:
            url = f"{self.base_url}/documents"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/pdf",
                "Content-Disposition": f'attachment; filename="{os.path.basename(pdf_file_path)}"',
            }
            with open(pdf_file_path, "rb") as pdf_file:
                response = requests.post(url, headers=headers, data=pdf_file)
                response.raise_for_status()
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error extracting metadata: {e}")
            return None

    def check_files_in_collection(self, access_token, collection_id):
        """Check if documents in a collection have files attached."""
        try:
            url = f"{self.base_url}/documents?collection_id={collection_id}"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            documents = response.json()
            return {doc["id"]: doc.get("file_attached", False) for doc in documents}
        except requests.exceptions.RequestException as e:
            print(f"Error checking files in collection: {e}")
            return None

    def list_documents_and_files_in_collection(self, access_token, collection_id):
        """List documents and their attached files in a given collection."""
        try:
            # Fetch documents in the collection
            url = f"{self.base_url}/documents?collection_id={collection_id}"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            documents = response.json()

            # Prepare a list to store documents and their files
            collection_data = []

            for document in documents:
                document_id = document.get("id")
                document_title = document.get("title", "Untitled")
                print(
                    f"Fetching files for document: {document_title} (ID: {document_id})"
                )

                # Fetch files attached to the document
                files = self.list_files(access_token, document_id)
                collection_data.append(
                    {
                        "document_id": document_id,
                        "document_title": document_title,
                        "files": files,
                    }
                )

            return collection_data
        except requests.exceptions.RequestException as e:
            print(f"Error listing documents and files in collection: {e}")
            return None

    def upload_file(self, access_token, document_id, file_path):
        """Upload a file to a document."""
        try:
            url = f"{self.base_url}/files"
            headers = {"Authorization": f"Bearer {access_token}"}
            with open(file_path, "rb") as file:
                files = {"file": file}
                data = {"document_id": document_id}
                response = requests.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()
                return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error uploading file: {e}")
            return None

    def list_files(self, access_token, document_id):
        """List files attached to a document."""
        try:
            url = f"{self.base_url}/files?document_id={document_id}"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error listing files: {e}")
            return None

    def download_file(self, access_token, file_id, save_path):
        """Download a file by its ID."""
        try:
            url = f"{self.base_url}/files/{file_id}"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers, stream=True)
            response.raise_for_status()
            with open(save_path, "wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            return save_path
        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {e}")
            return None


# Driver code to demonstrate usage
if __name__ == "__main__":
    # Load credentials from environment variables
    CLIENT_ID = os.getenv("MENDELEY_CLIENT_ID")
    CLIENT_SECRET = os.getenv("MENDELEY_SECRET_KEY")
    REDIRECT_URI = os.getenv("MENDELEY_REDIRECT_URI")

    # Create a folder for JSON data
    json_data_folder = os.path.join("mendeley_data", "json_data")
    os.makedirs(json_data_folder, exist_ok=True)

    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        raise RuntimeError(
            "Missing MENDELEY_CLIENT_ID, MENDELEY_SECRET_KEY, or MENDELEY_REDIRECT_URI in environment variables"
        )

    manager = MendeleyManager(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)

    # Step 1: Get authorization URL
    print("Authorization URL:", manager.get_auth_url())

    access_token = input("Enter the authorization access token: ")

    # Example usage of methods
    print("Listing documents...")
    documents = manager.list_documents(access_token)
    if not documents:
        print("No documents found.")
        exit()

    print("Listing collections...")
    collections = manager.list_collections(access_token)
    if not collections:
        print("No collections found.")
        exit()

    # print("Documents:", documents)
    # print("Collections:", collections)

    # Export the documents to a JSON file
    documents_file_path = os.path.join(json_data_folder, "documents.json")
    with open(documents_file_path, "w") as f:
        json.dump(documents, f, indent=2)
    print(f"Documents exported to {documents_file_path}")

    # Export the collections to a JSON file
    collections_file_path = os.path.join(json_data_folder, "collections.json")
    with open(collections_file_path, "w") as f:
        json.dump(collections, f, indent=2)
    print(f"Collections exported to {collections_file_path}")

    # Display collections and prompt user to select one
    print("Available collections:")
    for idx, collection in enumerate(collections):
        print(f"{idx + 1}. {collection.get('name')} (ID: {collection.get('id')})")

    collection_index = (
        int(input("Enter the number of the collection to list documents and files: "))
        - 1
    )
    if collection_index < 0 or collection_index >= len(collections):
        print("Invalid selection. Exiting.")
        exit()

    selected_collection = collections[collection_index]
    collection_id = selected_collection.get("id")
    collection_name = selected_collection.get("name")
    slugified_collection_name = slugify(collection_name)
    print(f"Selected collection: {collection_name} (ID: {collection_id})")

    # Step 4: List documents and files in the selected collection
    print(f"Listing documents and files in collection: {collection_name}")
    collection_data = manager.list_documents_and_files_in_collection(
        access_token, collection_id
    )
    if not collection_data:
        print("No documents or files found in the collection.")
        exit()

    # Display the documents and files
    for document in collection_data:
        print(f"Document: {document['document_title']} (ID: {document['document_id']})")
        if document["files"]:
            for file in document["files"]:
                print(f"  - File: {file.get('file_name')} (ID: {file.get('id')})")
        else:
            print("  - No files attached.")

    # Export the collection data to a JSON file
    collection_data_file_path = os.path.join(
        json_data_folder, f"{slugified_collection_name}_data.json"
    )
    with open(collection_data_file_path, "w") as f:
        json.dump(collection_data, f, indent=2)
    print(f"Collection data exported to {collection_data_file_path}")

    # Create a folder for downloaded files
    download_folder = "mendeley_data"
    os.makedirs(download_folder, exist_ok=True)

    downloaded_files = []
    for document in documents:
        document_id = document.get("id")
        document_title = document.get("title", "Untitled")
        print(f"Checking files for document: {document_title} (ID: {document_id})")

        # List files attached to the document
        files = manager.list_files(access_token, document_id)
        if files:
            for file in files:
                file_id = file.get("id")
                file_name = file.get("file_name", f"{document_title}.pdf")
                save_path = os.path.join(download_folder, file_name)
                print(f"Downloading file: {file_name}")
                downloaded_file = manager.download_file(
                    access_token, file_id, save_path
                )
                if downloaded_file:
                    downloaded_files.append(downloaded_file)
        else:
            print(f"No files attached to document: {document_title}")

    print(f"Downloaded files: {downloaded_files}")

    print("\nExtract metadata from a PDF file")
    pdf_file_path = input("Enter the path to the PDF file: ")
    if os.path.exists(pdf_file_path):
        metadata = manager.extract_metadata(access_token, pdf_file_path)
        if metadata:
            print("Extracted Metadata:")
            print(json.dumps(metadata, indent=2))

            # Export the metadata to a JSON file
            metadata_file_name = (
                os.path.splitext(os.path.basename(pdf_file_path))[0] + "_metadata.json"
            )
            metadata_file_path = os.path.join(json_data_folder, metadata_file_name)
            with open(metadata_file_path, "w") as metadata_file:
                json.dump(metadata, metadata_file, indent=2)
            print(f"Metadata exported to {metadata_file_path}")
        else:
            print("Failed to extract metadata.")
    else:
        print("The specified file does not exist.")
