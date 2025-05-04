import json
import os
import time
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()


class MendeleyAPIError(Exception):
    """Custom exception class to handle Mendeley API errors."""

    pass


class MendeleyClient:
    """
    A simple Python client for interacting with the Mendeley API.

    This class handles the OAuth2 flow (getting tokens, refreshing them)
    and provides methods for fetching folders, documents, and files.
    """

    def __init__(self, client_id, client_secret, redirect_uri):
        """
        :param client_id: Your Mendeley app's client ID
        :param client_secret: Your Mendeley app's client secret
        :param redirect_uri: The redirect URI registered with Mendeley
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

        # Mendeley endpoints
        self.auth_url = "https://api.mendeley.com/oauth/token"
        self.base_api_url = "https://api.mendeley.com"

        # Tokens and timing
        self.access_token = None
        self.refresh_token = None
        self.expires_in = None
        self.token_acquired_timestamp = None

    def get_authorization_url(self, scope="all", state="dummy_state"):
        """
        Generates the authorization URL to which the user should be redirected
        in order to grant access to this application.

        :param scope: The scope of permissions requested.
        :param state: A random string for security (CSRF protection).
        :return: A URL string for the Mendeley authorization page.
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
        url = f"https://api.mendeley.com/oauth/authorize?{urlencode(params)}"
        return url

    def exchange_code_for_token(self, code):
        """
        Exchange the authorization code for an access token and refresh token.

        :param code: The authorization code obtained from the callback
        """
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response = requests.post(self.auth_url, data=data)
            response.raise_for_status()  # Raise HTTPError if 4xx or 5xx
        except requests.RequestException as e:
            raise MendeleyAPIError(f"Error exchanging code for token: {str(e)}")

        token_data = response.json()
        self._store_token_data(token_data)

    def refresh_access_token(self):
        """
        Refresh the access token using the refresh token.
        """
        if not self.refresh_token:
            raise MendeleyAPIError(
                "No refresh token available to refresh the access token."
            )

        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }

        try:
            response = requests.post(self.auth_url, data=data)
            response.raise_for_status()
        except requests.RequestException as e:
            raise MendeleyAPIError(f"Error refreshing access token: {str(e)}")

        token_data = response.json()
        self._store_token_data(token_data)

    def _store_token_data(self, token_data):
        """
        Store token data from Mendeley’s OAuth server.
        """
        self.access_token = token_data.get("access_token")
        self.refresh_token = token_data.get("refresh_token")
        self.expires_in = token_data.get("expires_in")
        # Record when we obtained the token to know when it expires
        self.token_acquired_timestamp = time.time()

    def _is_token_expired(self):
        """
        Checks if the access token is close to expiration (or expired).
        Returns True if the token is invalid or about to expire.
        """
        if (
            not self.access_token
            or not self.expires_in
            or not self.token_acquired_timestamp
        ):
            return True  # No token is effectively expired

        # Give a 60-second buffer
        if time.time() >= (self.token_acquired_timestamp + self.expires_in - 60):
            return True

        return False

    def _ensure_token_valid(self):
        """
        Ensures we have a valid token; refreshes it if necessary.
        """
        if self._is_token_expired():
            self.refresh_access_token()

    def _get_headers(self):
        if not self.access_token:
            raise MendeleyAPIError(
                "Access token is missing. Please authenticate first."
            )
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def get_folders(self, limit=20, order="asc"):
        """
        Get a list of personal folders (collections) from the Mendeley API.

        :param limit: The number of folders to retrieve (optional).
        :param order: Sort order "asc" or "desc" (optional).
        :return: A list of folder objects.
        """
        self._ensure_token_valid()
        url = f"{self.base_api_url}/folders"
        params = {"limit": limit, "order": order}

        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
        except requests.RequestException as e:
            raise MendeleyAPIError(f"Error getting folders: {str(e)}")

        return response.json()

    def get_folder_by_id(self, folder_id):
        """
        Get the details of a specific folder.

        :param folder_id: The ID of the folder.
        :return: A dictionary with folder details.
        """
        self._ensure_token_valid()
        url = f"{self.base_api_url}/folders/{folder_id}"

        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
        except requests.RequestException as e:
            raise MendeleyAPIError(f"Error getting folder by ID {folder_id}: {str(e)}")

        return response.json()

    def get_documents_in_folder(self, folder_id, limit=20, order="asc"):
        """
        Get documents stored in a specific folder.

        :param folder_id: The ID of the folder.
        :param limit: The number of documents to retrieve (optional).
        :param order: Sort order "asc" or "desc" (optional).
        :return: A list of document objects.
        """
        self._ensure_token_valid()
        url = f"{self.base_api_url}/folders/{folder_id}/documents"
        params = {"limit": limit, "order": order}

        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
        except requests.RequestException as e:
            raise MendeleyAPIError(
                f"Error getting documents in folder {folder_id}: {str(e)}"
            )

        return response.json()

    def get_document(self, document_id):
        """
        Retrieve details for a specific document.

        :param document_id: The ID of the document.
        :return: A dictionary with document details.
        """
        self._ensure_token_valid()
        url = f"{self.base_api_url}/documents/{document_id}"

        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
        except requests.RequestException as e:
            raise MendeleyAPIError(f"Error getting document {document_id}: {str(e)}")

        return response.json()

    def get_files_for_document(self, document_id):
        """
        Retrieve the files attached to a specific document.

        :param document_id: The ID of the document.
        :return: A list of files (with metadata) attached to the document.
        """
        self._ensure_token_valid()
        url = f"{self.base_api_url}/files"
        params = {"document_id": document_id}

        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
        except requests.RequestException as e:
            raise MendeleyAPIError(
                f"Error getting files for document {document_id}: {str(e)}"
            )

        return response.json()


def main():
    """
    Example usage. In a real application, you would:
    1) Direct the user to `client.get_authorization_url()`
    2) Capture the authorization code from the redirect URI
    3) Call `client.exchange_code_for_token(code)`
    4) Then use the methods below to retrieve folders, documents, etc.
    """

    # Replace these placeholders with your own values
    CLIENT_ID = os.getenv("MENDELEY_CLIENT_ID")
    CLIENT_SECRET = os.getenv("MENDELEY_SECRET_KEY")
    REDIRECT_URI = os.getenv("LOCAL_MENDELEY_REDIRECT_URI")

    # Initialize the Mendeley client
    client = MendeleyClient(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)

    # --- STEP 1: Get the authorization URL and guide user to it ---
    auth_url = client.get_authorization_url()
    print("Please go to the following URL and authorize the application:")
    print(auth_url)

    # After authorization, Mendeley will redirect to your redirect URI with a ?code=<authorization_code>
    # Suppose you captured that code manually or via a small web server:
    # auth_code = input("Enter the authorization code: ")
    #
    # --- STEP 2: Exchange the code for a token ---
    # client.exchange_code_for_token(auth_code)

    # For demonstration, we won't actually do the full OAuth flow here.
    # We'll assume you have valid tokens now.

    # --- STEP 3: Use the client methods to interact with the Mendeley API ---
    # folders = client.get_folders()
    # for folder in folders:
    #     print(folder)

    # folder_id = "some_folder_id"
    # folder_data = client.get_folder_by_id(folder_id)
    # print(folder_data)

    # documents_in_folder = client.get_documents_in_folder(folder_id)
    # print(documents_in_folder)

    # doc_id = "some_document_id"
    # document_data = client.get_document(doc_id)
    # print(document_data)

    # files = client.get_files_for_document(doc_id)
    # print(files)


if __name__ == "__main__":
    main()
