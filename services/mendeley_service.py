import json
import os

from utils.mendeley_manager import MendeleyManager


class MendeleyService:
    def __init__(self, client_id, client_secret, redirect_uri):
        self.manager = MendeleyManager(client_id, client_secret, redirect_uri)

    def get_auth_url(self):
        """Retrieve the authorization URL."""
        return self.manager.get_auth_url()

    def list_collections(self, access_token):
        """Retrieve all collections (folders) in your Mendeley account."""
        return self.manager.list_collections(access_token)

    def list_documents(self, access_token, collection_id=None):
        """Retrieve all documents in your Mendeley library or a specific collection."""
        if collection_id:
            return self.manager.list_documents_and_files_in_collection(
                access_token, collection_id
            )
        return self.manager.list_documents(access_token)

    def check_files(self, access_token, collection_id):
        """Check if documents in a collection have files attached."""
        return self.manager.check_files_in_collection(access_token, collection_id)

    def download_files(
        self, access_token, collection_id, download_folder="mendeley_data"
    ):
        """Download attached files for a given collection to a local directory."""
        os.makedirs(download_folder, exist_ok=True)
        collection_data = self.manager.list_documents_and_files_in_collection(
            access_token, collection_id
        )
        downloaded_files = []

        for document in collection_data:
            document_title = document.get("document_title", "Untitled")
            for file in document.get("files", []):
                file_id = file.get("id")
                file_name = file.get("file_name", f"{document_title}.pdf")
                save_path = os.path.join(download_folder, file_name)
                downloaded_file = self.manager.download_file(
                    access_token, file_id, save_path
                )
                if downloaded_file:
                    downloaded_files.append(downloaded_file)

        return downloaded_files

    def extract_metadata(
        self, access_token, pdf_file_path, output_folder="mendeley_data/json_data"
    ):
        """Extract metadata for a given file."""
        os.makedirs(output_folder, exist_ok=True)
        metadata = self.manager.extract_metadata(access_token, pdf_file_path)
        if metadata:
            metadata_file_name = (
                os.path.splitext(os.path.basename(pdf_file_path))[0] + "_metadata.json"
            )
            metadata_file_path = os.path.join(output_folder, metadata_file_name)
            with open(metadata_file_path, "w") as metadata_file:
                json.dump(metadata, metadata_file, indent=2)
            return metadata_file_path
        return None

    def export_data(self, access_token, output_folder="mendeley_data/json_data"):
        """Export collections and document data to JSON files."""
        os.makedirs(output_folder, exist_ok=True)

        # Export collections
        collections = self.manager.list_collections(access_token)
        collections_file_path = os.path.join(output_folder, "collections.json")
        with open(collections_file_path, "w") as f:
            json.dump(collections, f, indent=2)

        # Export documents
        documents = self.manager.list_documents(access_token)
        documents_file_path = os.path.join(output_folder, "documents.json")
        with open(documents_file_path, "w") as f:
            json.dump(documents, f, indent=2)

        return {
            "collections_file": collections_file_path,
            "documents_file": documents_file_path,
        }
