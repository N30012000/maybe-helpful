# drive_store.py
import io
import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload

class GoogleDriveBackend:
    def __init__(self):
        # Authenticate silently in the background
        secret_info = dict(st.secrets["google_drive"])
        secret_info["private_key"] = secret_info["private_key"].replace("\\n", "\n")
        
        self.scopes = ["https://www.googleapis.com/auth/drive"]
        self.creds = service_account.Credentials.from_service_account_info(
            secret_info, scopes=self.scopes
        )
        self.service = build("drive", "v3", credentials=self.creds)
        self.folder_id = secret_info["folder_id"]

    def upload_pdf(self, file_name: str, file_bytes: bytes) -> str:
        """Uploads a PDF and returns the Drive File ID"""
        file_metadata = {
            "name": file_name,
            "parents": [self.folder_id],
            "mimeType": "application/pdf"
        }
        media = MediaIoBaseUpload(
            io.BytesIO(file_bytes), mimetype="application/pdf", resumable=True
        )
        uploaded_file = self.service.files().create(
            body=file_metadata, media_body=media, fields="id"
        ).execute()
        return uploaded_file.get("id")

    def fetch_pdf(self, file_id: str) -> bytes:
        """Downloads a PDF from Drive using its file ID"""
        request = self.service.files().get_media(fileId=file_id)
        file_buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(file_buffer, request)
        
        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        return file_buffer.getvalue()

    def list_saved_pdfs(self) -> list:
        """Lists files inside our designated folder"""
        query = f"'{self.folder_id}' in parents and trashed = false"
        results = self.service.files().list(
            q=query, fields="files(id, name)"
        ).execute()
        return results.get("files", [])
