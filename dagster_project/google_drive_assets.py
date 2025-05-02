import os
import json
from typing import Dict, List, Any, Optional
import logging
import requests
from datetime import datetime, timedelta
import pickle
import hashlib

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from elasticsearch import Elasticsearch
from neo4j import GraphDatabase

from dagster import (
    asset,
    AssetExecutionContext,
    MetadataValue,
    Config, 
    Definitions,
    ScheduleDefinition,
    define_asset_job,
    AssetKey,
    EnvVar,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration class for Google Drive assets
class GoogleDriveConfig(Config):
    credentials_file: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "credentials.json")
    haystack_api_url: str = os.getenv("HAYSTACK_API_URL", "http://haystack:8000")
    file_types: List[str] = [
        ".txt", ".md", ".pdf", ".docx",  # Regular files
        "application/vnd.google-apps.document",  # Google Docs
        "application/vnd.google-apps.spreadsheet",  # Google Sheets
        "application/vnd.google-apps.presentation"  # Google Slides
    ]
    max_files: int = 1000
    recursive: bool = True  # Whether to recursively traverse folders

# Initialize connections
es = Elasticsearch(
    hosts=[{
        'scheme': 'http',
        'host': os.getenv("ELASTICSEARCH_HOST", "elasticsearch"),
        'port': int(os.getenv("ELASTICSEARCH_PORT", "9200"))
    }]
)
neo4j_driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
    auth=(
        os.getenv("NEO4J_USER", "neo4j"),
        os.getenv("NEO4J_PASSWORD", "password")
    )
)

# Google Drive setup
SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

def get_google_drive_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('drive', 'v3', credentials=creds)

@asset(group_name="company_doc_imports")
def google_drive_service(context: AssetExecutionContext, config: GoogleDriveConfig):
    """Create and return a Google Drive service instance."""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            config.credentials_file,
            scopes=SCOPES
        )
        service = build('drive', 'v3', credentials=credentials)
        
        # Verify service with a simple API call and log service account email
        about = service.about().get(fields="user").execute()
        service_email = about.get("user", {}).get("emailAddress", "unknown")
        context.log.info(f"Service account email: {service_email}")
        context.add_output_metadata({
            "service_email": MetadataValue.text(service_email)
        })
        
        return service
    except Exception as e:
        logger.error(f"Error creating Google Drive service: {e}")
        raise

def fetch_files_recursive(service, folder_id, context, config, depth=0, max_depth=10, parent_id=None):
    """
    Recursively fetch files and folders from a folder and its subfolders, tracking parent relationships.
    Returns:
        Dict with 'files' and 'folders' lists.
    """
    if depth > max_depth:
        context.log.warning(f"Reached maximum recursion depth ({max_depth}) for folder {folder_id}")
        return {"files": [], "folders": []}

    all_files = []
    all_folders = []

    try:
        # Get folder info
        folder_info = service.files().get(fileId=folder_id, fields="name,id").execute()
        folder_name = folder_info.get("name", folder_id)
        # Track this folder and its parent
        all_folders.append({"id": folder_id, "name": folder_name, "parent_id": parent_id})
        context.log.info(f"Processing folder (depth {depth}): {folder_name} ({folder_id})")
        query = f"'{folder_id}' in parents and trashed = false"
        page_token = None
        files_processed = 0
        while True:
            if files_processed >= config.max_files:
                context.log.info(f"Reached max files limit ({config.max_files}) for folder {folder_name}")
                break
            context.log.info(f"Querying files in folder {folder_name} (batch {files_processed//100 + 1})")
            response = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink)",
                pageToken=page_token,
                pageSize=min(100, config.max_files - files_processed)
            ).execute()
            items = response.get('files', [])
            context.log.info(f"Found {len(items)} items in this batch")
            for item in items:
                context.log.info(f"Processing item: {item['name']} (Type: {item['mimeType']})")
                mime_type = item['mimeType']
                if mime_type == 'application/vnd.google-apps.folder' and config.recursive:
                    context.log.info(f"Recursively processing subfolder: {item['name']}")
                    sub_result = fetch_files_recursive(
                        service,
                        item['id'],
                        context,
                        config,
                        depth + 1,
                        max_depth,
                        parent_id=folder_id
                    )
                    all_files.extend(sub_result["files"])
                    all_folders.extend(sub_result["folders"])
                    context.log.info(f"Completed processing subfolder {item['name']}, found {len(sub_result['files'])} files and {len(sub_result['folders'])} folders")
                else:
                    mime_type_supported = mime_type in config.file_types
                    extension_supported = any(
                        ext.startswith('.') and item['name'].lower().endswith(ext.lower())
                        for ext in config.file_types
                    )
                    context.log.info(f"File type checks for {item['name']}:")
                    context.log.info(f"  MIME type: {mime_type}")
                    context.log.info(f"  MIME type supported: {mime_type_supported}")
                    context.log.info(f"  Extension supported: {extension_supported}")
                    context.log.info(f"  Supported types: {config.file_types}")
                    if mime_type_supported or extension_supported:
                        context.log.info(f"Processing file: {item['name']}")
                        try:
                            perms = service.permissions().list(
                                fileId=item['id'],
                                fields="permissions(id,type,emailAddress,role,domain)"
                            ).execute()
                            item['detailed_permissions'] = perms.get('permissions', [])
                        except Exception as e:
                            context.log.warning(f"Could not get permissions for {item['name']}, will process with basic permissions: {e}")
                            item['detailed_permissions'] = [{
                                'type': 'user',
                                'role': 'unknown',
                                'emailAddress': context.run_id if hasattr(context, 'run_id') else 'service_account',
                                'note': 'Could not retrieve full permissions; this is a fallback entry.'
                            }]
                        # Set parent_id for every file
                        item['parent_id'] = folder_id
                        all_files.append(item)
                        files_processed += 1
                        context.log.info(f"Successfully processed file: {item['name']}")
                    else:
                        context.log.info(f"Skipping unsupported file type: {item['name']} ({mime_type})")
            page_token = response.get('nextPageToken')
            if not page_token or files_processed >= config.max_files:
                context.log.info(f"Completed processing folder {folder_name}, found {len(all_files)} files")
                break
    except HttpError as error:
        context.log.error(f"Error accessing folder {folder_id}: {error}")
    return {"files": all_files, "folders": all_folders}

def list_shared_resources(service, context):
    """List all files and folders shared with the service account."""
    shared_files = []
    page_token = None
    
    context.log.info("Starting to list shared resources...")
    
    while True:
        try:
            # Query for files shared with the service account
            context.log.info("Querying Google Drive API for shared resources...")
            response = service.files().list(
                q="sharedWithMe=true and trashed=false",
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink)',  # Simplified fields
                pageToken=page_token,
                pageSize=100
            ).execute()
            
            items = response.get('files', [])
            if not items:
                context.log.info("No more shared resources found.")
                break
                
            context.log.info(f"Found {len(items)} shared resources in this batch")
            
            for item in items:
                context.log.info(f"Processing shared resource: {item['name']} (ID: {item['id']})")
                shared_files.append(item)
            
            page_token = response.get('nextPageToken')
            if not page_token:
                context.log.info("Reached end of shared resources list")
                break
                
        except HttpError as error:
            context.log.error(f"Error listing shared resources: {error}")
            break
            
    context.log.info(f"Total shared resources found: {len(shared_files)}")
    return shared_files

@asset(group_name="company_doc_imports")
def google_drive_files(context: AssetExecutionContext, config: GoogleDriveConfig, google_drive_service):
    """Fetch files and folders from Google Drive folders with permissions."""
    service = google_drive_service
    shared_files = list_shared_resources(service, context)
    all_files = []
    all_folders = []
    total_size = 0
    for file in shared_files:
        try:
            mime_type = file['mimeType']
            if mime_type == 'application/vnd.google-apps.folder' and config.recursive:
                result = fetch_files_recursive(service, file['id'], context, config, parent_id=None)
                all_files.extend(result["files"])
                all_folders.extend(result["folders"])
            elif mime_type in config.file_types or any(file['name'].endswith(ext) for ext in config.file_types if ext.startswith('.')):
                file['parent_id'] = None
                all_files.append(file)
                total_size += int(file.get('size', 0))
        except HttpError as error:
            context.log.error(f"Error processing file {file.get('name', 'unknown')}: {error}")
    context.add_output_metadata({
        "num_files": len(all_files),
        "num_folders": len(all_folders),
        "total_size_bytes": total_size,
        "recursive_mode": MetadataValue.text("Enabled" if config.recursive else "Disabled"),
        "preview": MetadataValue.json(all_files[:5] if all_files else [])
    })
    return {"files": all_files, "folders": all_folders}

def compute_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

@asset(group_name="company_doc_imports")
def index_files(
    context: AssetExecutionContext,
    config: GoogleDriveConfig,
    google_drive_files: dict,
    google_drive_service
):
    """Index Google Drive files and folders in Elasticsearch and Neo4j."""
    service = google_drive_service
    files = google_drive_files["files"]
    folders = google_drive_files["folders"]
    indexed_files = []
    failed_files = []
    
    # First, create all folders and their relationships in Neo4j
    with neo4j_driver.session() as session:
        for folder in folders:
            session.run(
                """
                MERGE (f:Folder {id: $id})
                SET f.name = $name
                """,
                {"id": folder["id"], "name": folder["name"]}
            )
            if folder["parent_id"]:
                session.run(
                    """
                    MATCH (parent:Folder {id: $parent_id}), (child:Folder {id: $id})
                    MERGE (parent)-[:CONTAINS]->(child)
                    """,
                    {"parent_id": folder["parent_id"], "id": folder["id"]}
                )
    
    # Now process files
    for file in files:
        try:
            file_id = file['id']
            file_name = file['name']
            mime_type = file['mimeType']
            if 'google-apps' in mime_type:
                try:
                    export_mime_type = 'text/plain'
                    content = service.files().export(fileId=file_id, mimeType=export_mime_type).execute()
                except HttpError as e:
                    context.log.warning(f"Could not access content of {file_name} (ID: {file_id}). This is likely a permissions issue. Error: {e}")
                    content = f"[Content not accessible - insufficient permissions]\nFile Name: {file_name}\nType: {mime_type}\nWeb Link: {file.get('webViewLink', 'Not available')}"
            else:
                try:
                    content = service.files().get_media(fileId=file_id).execute()
                except HttpError as e:
                    context.log.warning(f"Could not download {file_name} (ID: {file_id}). This is likely a permissions issue. Error: {e}")
                    content = f"[Content not accessible - insufficient permissions]\nFile Name: {file_name}\nType: {mime_type}\nWeb Link: {file.get('webViewLink', 'Not available')}"
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
            else:
                content_bytes = content
            content_hash = compute_hash(content_bytes)
            try:
                existing = es.get(index="google_drive_files", id=file_id, ignore=[404])
            except Exception:
                existing = None
            if existing and existing.get('_source', {}).get('meta', {}).get('content_hash') == content_hash:
                context.log.info(f"Skipping reindex for {file_name}: content hash unchanged.")
                continue
            permissions = []
            is_public = False
            accessible_by_emails = []
            accessible_by_domains = []
            permissions_incomplete = False
            for perm in file.get('detailed_permissions', []):
                permission_entry = {
                    "type": perm.get('type'),
                    "role": perm.get('role'),
                }
                if 'note' in perm:
                    permission_entry['note'] = perm['note']
                    permissions_incomplete = True
                if perm.get('type') == 'anyone' and perm.get('role') in ['reader', 'writer', 'owner']:
                    is_public = True
                if 'emailAddress' in perm:
                    permission_entry['email'] = perm['emailAddress']
                    accessible_by_emails.append(perm['emailAddress'])
                if 'domain' in perm:
                    permission_entry['domain'] = perm['domain']
                    accessible_by_domains.append(perm['domain'])
                permissions.append(permission_entry)
            metadata = {
                "source": f"google_drive:{file_id}",
                "file_id": file_id,
                "file_name": file_name,
                "mime_type": mime_type,
                "created_time": file.get('createdTime'),
                "modified_time": file.get('modifiedTime'),
                "web_link": file.get('webViewLink'),
                "permissions": permissions,
                "is_public": is_public,
                "accessible_by_emails": accessible_by_emails,
                "accessible_by_domains": accessible_by_domains,
                "permissions_incomplete": permissions_incomplete,
                "content_hash": content_hash
            }
            es.index(
                index="google_drive_files",
                id=file_id,
                document={
                    "content": content.decode('utf-8') if isinstance(content, bytes) else content,
                    "meta": metadata
                }
            )
            # Neo4j indexing with better parent folder handling
            context.log.info(f"File {file_id} has parent_id: {file.get('parent_id')}")
            print(f"DEBUG: File {file_id} ({file_name}) parent_id: {file.get('parent_id')}")
            with neo4j_driver.session() as session:
                # Create or update file node and optionally link to parent
                session.run(
                    """
                    MERGE (f:File {id: $file_id})
                    SET f.name = $file_name,
                        f.mime_type = $mime_type,
                        f.created_time = $created_time,
                        f.modified_time = $modified_time,
                        f.web_link = $web_link,
                        f.is_public = $is_public
                    WITH f
                    OPTIONAL MATCH (parent:Folder {id: $parent_id})
                    WITH f, parent
                    WHERE parent IS NOT NULL
                    MERGE (parent)-[:CONTAINS]->(f)
                    """,
                    {
                        "file_id": file_id,
                        "file_name": file_name,
                        "mime_type": mime_type,
                        "created_time": file.get('createdTime'),
                        "modified_time": file.get('modifiedTime'),
                        "web_link": file.get('webViewLink'),
                        "is_public": is_public,
                        "parent_id": file.get('parent_id')
                    }
                )
                context.log.info(f"Created file node and relationship for {file_name}")
                
                # Create user and domain relationships
                for email in accessible_by_emails:
                    session.run(
                        """
                        MERGE (u:User {email: $email})
                        WITH u
                        MATCH (f:File {id: $file_id})
                        MERGE (f)-[:ACCESSIBLE_BY]->(u)
                        """,
                        {"email": email, "file_id": file_id}
                    )
                for domain in accessible_by_domains:
                    session.run(
                        """
                        MERGE (d:Domain {name: $domain})
                        WITH d
                        MATCH (f:File {id: $file_id})
                        MERGE (f)-[:ACCESSIBLE_BY_DOMAIN]->(d)
                        """,
                        {"domain": domain, "file_id": file_id}
                    )
            indexed_files.append(file_id)
            context.log.info(f"Successfully indexed: {file_name}")
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
    selection=[index_files]
)

# Define schedules
google_drive_schedule = ScheduleDefinition(
    job=google_drive_indexing_job,
    cron_schedule="0 */6 * * *",  # Run every 6 hours
)

# Create definitions object
defs = Definitions(
    assets=[google_drive_service, google_drive_files, index_files],
    schedules=[google_drive_schedule],
    jobs=[google_drive_indexing_job],
) 