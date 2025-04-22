import os
import json
from typing import Dict, List, Any, Optional
import logging
import requests
from datetime import datetime, timedelta

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from dagster import (
    asset,
    AssetExecutionContext,
    MetadataValue,
    Config, 
    Definitions,
    ScheduleDefinition,
    define_asset_job,
    AssetKey,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration class for Google Drive assets
class GoogleDriveConfig(Config):
    credentials_file: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
    haystack_api_url: str = os.getenv("HAYSTACK_API_URL", "http://haystack:8000")
    folder_ids: List[str] = [] 
    file_types: List[str] = [".txt", ".md", ".pdf", ".docx"]
    max_files: int = 100

@asset
def google_drive_service(context: AssetExecutionContext, config: GoogleDriveConfig):
    """Create and return a Google Drive service instance."""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            config.credentials_file,
            scopes=['https://www.googleapis.com/auth/drive.readonly']
        )
        service = build('drive', 'v3', credentials=credentials)
        
        # Verify service with a simple API call
        about = service.about().get(fields="user").execute()
        context.add_output_metadata({
            "service_email": MetadataValue.text(about.get("user", {}).get("emailAddress", "unknown"))
        })
        
        return service
    except Exception as e:
        logger.error(f"Error creating Google Drive service: {e}")
        raise

@asset(deps=[google_drive_service])
def google_drive_files(context: AssetExecutionContext, config: GoogleDriveConfig, google_drive_service):
    """Fetch files from Google Drive folders with permissions."""
    service = google_drive_service
    
    all_files = []
    total_size = 0
    
    # Use provided folder IDs or fall back to "root"
    folder_ids = config.folder_ids if config.folder_ids else ['root']
    
    for folder_id in folder_ids:
        try:
            # Get folder info
            folder_info = service.files().get(fileId=folder_id, fields="name,id").execute()
            folder_name = folder_info.get("name", folder_id)
            
            context.log.info(f"Processing folder: {folder_name} ({folder_id})")
            
            # Query files in the folder
            query = f"'{folder_id}' in parents and trashed = false"
            response = service.files().list(
                q=query,
                fields="files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink, permissions)",
                pageSize=config.max_files
            ).execute()
            
            files = response.get('files', [])
            
            # Get detailed permission info for each file
            for file in files:
                # Filter by supported file types
                if not any(file['name'].endswith(ext) for ext in config.file_types):
                    continue
                
                # Get permissions
                try:
                    perms = service.permissions().list(
                        fileId=file['id'], 
                        fields="permissions(id,type,emailAddress,role,domain)"
                    ).execute()
                    file['detailed_permissions'] = perms.get('permissions', [])
                    
                    # Add file to our collection
                    all_files.append(file)
                    total_size += int(file.get('size', 0))
                except Exception as e:
                    context.log.warning(f"Error getting permissions for {file['name']}: {e}")
        
        except HttpError as error:
            context.log.error(f"Error accessing folder {folder_id}: {error}")
    
    context.add_output_metadata({
        "num_files": len(all_files),
        "total_size_bytes": total_size,
        "preview": MetadataValue.json(all_files[:5] if all_files else [])
    })
    
    return all_files

@asset(deps=[google_drive_files])
def haystack_indexed_files(
    context: AssetExecutionContext,
    config: GoogleDriveConfig,
    google_drive_files: List[Dict[str, Any]],
    google_drive_service
):
    """Index Google Drive files in Haystack."""
    service = google_drive_service
    
    # Group files by their required permission levels
    indexed_files = []
    failed_files = []
    
    for file in google_drive_files:
        try:
            # Get file content
            file_id = file['id']
            file_name = file['name']
            mime_type = file['mimeType']
            
            # Download file content based on mime type
            if 'google-apps' in mime_type:
                # For Google Docs/Sheets/etc., export as text
                export_mime_type = 'text/plain'
                content = service.files().export(fileId=file_id, mimeType=export_mime_type).execute()
            else:
                # For regular files, download directly
                content = service.files().get_media(fileId=file_id).execute()
            
            # Extract permissions info for metadata
            permissions = []
            for perm in file.get('detailed_permissions', []):
                permission_entry = {
                    "type": perm.get('type'),
                    "role": perm.get('role'),
                }
                
                if 'emailAddress' in perm:
                    permission_entry['email'] = perm['emailAddress']
                if 'domain' in perm:
                    permission_entry['domain'] = perm['domain']
                    
                permissions.append(permission_entry)
            
            # Prepare document metadata
            metadata = {
                "source": f"google_drive:{file_id}",
                "file_id": file_id,
                "file_name": file_name, 
                "mime_type": mime_type,
                "created_time": file.get('createdTime'),
                "modified_time": file.get('modifiedTime'),
                "web_link": file.get('webViewLink'),
                "permissions": permissions
            }
            
            # Index in Haystack
            indexing_response = requests.post(
                f"{config.haystack_api_url}/search",
                json={
                    "query": "",  # Empty query for indexing
                    "action": "index",
                    "document": {
                        "content": content.decode('utf-8') if isinstance(content, bytes) else content,
                        "meta": metadata
                    }
                }
            )
            
            if indexing_response.status_code == 200:
                indexed_files.append(file_id)
                context.log.info(f"Successfully indexed: {file_name}")
            else:
                context.log.error(f"Failed to index {file_name}: {indexing_response.text}")
                failed_files.append(file_id)
                
        except Exception as e:
            context.log.error(f"Error processing file {file.get('name', 'unknown')}: {e}")
            failed_files.append(file.get('id', 'unknown'))
    
    context.add_output_metadata({
        "indexed_count": len(indexed_files),
        "failed_count": len(failed_files),
        "indexed_files": MetadataValue.json(indexed_files[:5] if indexed_files else []),
        "failed_files": MetadataValue.json(failed_files[:5] if failed_files else [])
    })
    
    return {
        "indexed_files": indexed_files,
        "failed_files": failed_files
    }

# Define jobs
google_drive_indexing_job = define_asset_job(
    name="google_drive_indexing_job",
    selection=[google_drive_service, google_drive_files, haystack_indexed_files]
)

# Define schedules
google_drive_schedule = ScheduleDefinition(
    job=google_drive_indexing_job,
    cron_schedule="0 */6 * * *",  # Run every 6 hours
)

# Create definitions object
defs = Definitions(
    assets=[google_drive_service, google_drive_files, haystack_indexed_files],
    schedules=[google_drive_schedule],
    jobs=[google_drive_indexing_job],
) 