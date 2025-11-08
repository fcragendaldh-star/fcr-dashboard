"""
Google Drive Storage Integration Module
Handles file operations with Google Drive
"""

import os
import logging
from typing import List, Optional
from io import BytesIO
import json

logger = logging.getLogger(__name__)

class GoogleDriveStorage:
    """Google Drive Storage Implementation"""
    
    def __init__(self):
        # Try to get secrets from Streamlit first (for Streamlit Cloud)
        # Then fall back to environment variables (for local development)
        self.folder_id = ""
        self.credentials_json = ""
        
        # Try Streamlit secrets first
        try:
            import streamlit as st
            try:
                # Access Streamlit secrets - they're available as a dict-like object
                self.folder_id = st.secrets["GOOGLE_DRIVE_FOLDER_ID"]
                self.credentials_json = st.secrets["GOOGLE_APPLICATION_CREDENTIALS_JSON"]
                logger.info("✓ Loaded credentials from Streamlit secrets")
            except KeyError as e:
                logger.warning(f"Secret key not found in st.secrets: {e}")
            except Exception as e:
                logger.warning(f"Error accessing st.secrets: {e}")
        except ImportError:
            logger.info("Streamlit not available, will use environment variables")
        except Exception as e:
            logger.warning(f"Unexpected error accessing Streamlit: {e}")
        
        # Fall back to environment variables if Streamlit secrets not available
        if not self.folder_id:
            self.folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")
            if self.folder_id:
                logger.info("✓ Loaded GOOGLE_DRIVE_FOLDER_ID from environment variable")
        if not self.credentials_json:
            self.credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "")
            if self.credentials_json:
                logger.info("✓ Loaded GOOGLE_APPLICATION_CREDENTIALS_JSON from environment variable")
        
        # Validate that we have both required values
        if not self.folder_id:
            error_msg = "GOOGLE_DRIVE_FOLDER_ID not set in Streamlit secrets or environment variables"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        if not self.credentials_json:
            error_msg = "GOOGLE_APPLICATION_CREDENTIALS_JSON not set in Streamlit secrets or environment variables"
            logger.error(f"❌ {error_msg}")
            raise ValueError(error_msg)
        
        logger.info(f"✓ Folder ID: {self.folder_id[:20]}...")
        logger.info(f"✓ Credentials JSON length: {len(self.credentials_json)} characters")
        
        # Initialize Google Drive API client
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
            from googleapiclient.errors import HttpError
            
            # Parse credentials from JSON string
            try:
                # Try to parse as JSON string first
                if isinstance(self.credentials_json, str):
                    creds_dict = json.loads(self.credentials_json)
                else:
                    # Already a dict
                    creds_dict = self.credentials_json
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON in GOOGLE_APPLICATION_CREDENTIALS_JSON: {str(e)}"
                logger.error(f"❌ {error_msg}")
                logger.error(f"JSON preview (first 100 chars): {self.credentials_json[:100]}")
                raise ValueError(error_msg)
            
            # Validate required fields
            required_fields = ['type', 'project_id', 'private_key', 'client_email']
            missing_fields = [field for field in required_fields if field not in creds_dict]
            if missing_fields:
                error_msg = f"Missing required fields in credentials: {', '.join(missing_fields)}"
                logger.error(f"❌ {error_msg}")
                raise ValueError(error_msg)
            
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=['https://www.googleapis.com/auth/drive']
            )
            
            self.drive_service = build('drive', 'v3', credentials=credentials)
            self.MediaIoBaseDownload = MediaIoBaseDownload
            self.MediaIoBaseUpload = MediaIoBaseUpload
            self.HttpError = HttpError
            
            logger.info("✓ Google Drive API initialized successfully")
        except ImportError:
            raise ImportError("google-api-python-client and google-auth are required. Install with: pip install google-api-python-client google-auth")
        except ValueError:
            # Re-raise ValueError as-is (already formatted)
            raise
        except Exception as e:
            logger.error(f"❌ Error initializing Google Drive API: {e}")
            raise
    
    def list_files(self) -> List[dict]:
        """List all Excel files in the Google Drive folder"""
        try:
            # Query files in the folder
            query = f"'{self.folder_id}' in parents and (mimeType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' or mimeType='application/vnd.ms-excel') and trashed=false"
            
            results = self.drive_service.files().list(
                q=query,
                fields="files(id, name, createdTime, modifiedTime)",
                orderBy="modifiedTime desc"
            ).execute()
            
            files = results.get('files', [])
            logger.info(f"Found {len(files)} files in Google Drive folder")
            return files
            
        except self.HttpError as e:
            logger.error(f"Error listing files from Google Drive: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing files: {e}")
            return []
    
    def download_file(self, file_id: str) -> BytesIO:
        """Download file from Google Drive by file ID"""
        try:
            request = self.drive_service.files().get_media(fileId=file_id)
            file_data = BytesIO()
            downloader = self.MediaIoBaseDownload(file_data, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
            
            file_data.seek(0)
            return file_data
            
        except self.HttpError as e:
            logger.error(f"Error downloading file {file_id} from Google Drive: {e}")
            return BytesIO()
        except Exception as e:
            logger.error(f"Unexpected error downloading file: {e}")
            return BytesIO()
    
    def upload_file(self, file_data: bytes, filename: str) -> Optional[str]:
        """Upload file to Google Drive folder"""
        try:
            from googleapiclient.http import MediaIoBaseUpload
            
            file_metadata = {
                'name': filename,
                'parents': [self.folder_id]
            }
            
            media = MediaIoBaseUpload(
                BytesIO(file_data),
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                resumable=True
            )
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name'
            ).execute()
            
            logger.info(f"File {filename} uploaded to Google Drive with ID: {file.get('id')}")
            return file.get('id')
            
        except self.HttpError as e:
            logger.error(f"Error uploading file {filename} to Google Drive: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading file: {e}")
            return None
    
    def delete_file(self, file_id: str) -> bool:
        """Delete file from Google Drive by file ID"""
        try:
            self.drive_service.files().delete(fileId=file_id).execute()
            logger.info(f"File {file_id} deleted from Google Drive")
            return True
        except self.HttpError as e:
            logger.error(f"Error deleting file {file_id} from Google Drive: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting file: {e}")
            return False
    
    def get_file_by_name(self, filename: str) -> Optional[dict]:
        """Get file information by filename"""
        files = self.list_files()
        for file in files:
            if file['name'] == filename:
                return file
        return None

