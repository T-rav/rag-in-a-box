import os
import json
from typing import Dict, List, Any, Optional
import logging
import requests
from datetime import datetime, timedelta
import pickle

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
    file_types: List[str] = [".txt", ".md", ".pdf", ".docx"]
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
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

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

def fetch_files_recursive(service, folder_id, context, config, depth=0, max_depth=10):
    """
    Recursively fetch files from a folder and its subfolders
    
    Args:
        service: Google Drive service instance
        folder_id: ID of the folder to process
        context: Dagster execution context
        config: Configuration object
        depth: Current recursion depth
        max_depth: Maximum recursion depth to prevent infinite loops
        
    Returns:
        List of file metadata dictionaries
    """
    if depth > max_depth:
        context.log.warning(f"Reached maximum recursion depth ({max_depth}) for folder {folder_id}")
        return []
        
    all_files = []
    
    try:
        # Get folder info
        folder_info = service.files().get(fileId=folder_id, fields="name,id").execute()
        folder_name = folder_info.get("name", folder_id)
        
        context.log.info(f"Processing folder (depth {depth}): {folder_name} ({folder_id})")
        
        # Query files in the folder
        query = f"'{folder_id}' in parents and trashed = false"
        
        # Process files in batches with pagination to handle large folders
        page_token = None
        files_processed = 0
        
        while True:
            # Check if we've reached the max files limit
            if files_processed >= config.max_files:
                context.log.info(f"Reached max files limit ({config.max_files}) for folder {folder_name}")
                break
                
            response = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink, permissions)",
                pageToken=page_token,
                pageSize=min(100, config.max_files - files_processed)  # Process in batches of up to 100
            ).execute()
            
            items = response.get('files', [])
            
            for item in items:
                # If it's a folder and recursive is enabled, process it recursively
                if item['mimeType'] == 'application/vnd.google-apps.folder' and config.recursive:
                    subfolder_files = fetch_files_recursive(
                        service, 
                        item['id'], 
                        context, 
                        config, 
                        depth + 1,
                        max_depth
                    )
                    all_files.extend(subfolder_files)
                    
                # For files, check if they match the supported file types
                elif any(item['name'].endswith(ext) for ext in config.file_types):
                    # Get detailed permissions
                    try:
                        perms = service.permissions().list(
                            fileId=item['id'], 
                            fields="permissions(id,type,emailAddress,role,domain)"
                        ).execute()
                        item['detailed_permissions'] = perms.get('permissions', [])
                        
                        # Add file to our collection
                        all_files.append(item)
                        files_processed += 1
                    except Exception as e:
                        context.log.warning(f"Error getting permissions for {item['name']}: {e}")
            
            # Get the next page token
            page_token = response.get('nextPageToken')
            
            # Break if no more pages or we've reached the file limit
            if not page_token or files_processed >= config.max_files:
                break
                
    except HttpError as error:
        context.log.error(f"Error accessing folder {folder_id}: {error}")
        
    return all_files

def list_shared_resources(service, context):
    """List all files and folders shared with the service account."""
    shared_files = []
    page_token = None
    
    while True:
        try:
            # Query for files shared with the service account
            response = service.files().list(
                q="sharedWithMe=true and trashed=false",
                spaces='drive',
                fields='nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink, permissions, parents)',
                pageToken=page_token,
                pageSize=100
            ).execute()
            
            items = response.get('files', [])
            if not items:
                break
                
            for item in items:
                # Get detailed permissions
                try:
                    perms = service.permissions().list(
                        fileId=item['id'], 
                        fields="permissions(id,type,emailAddress,role,domain)"
                    ).execute()
                    item['detailed_permissions'] = perms.get('permissions', [])
                    shared_files.append(item)
                except Exception as e:
                    context.log.warning(f"Error getting permissions for {item['name']}: {e}")
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
                
        except HttpError as error:
            context.log.error(f"Error listing shared resources: {error}")
            break
            
    return shared_files

@asset
def google_drive_files(context: AssetExecutionContext, config: GoogleDriveConfig, google_drive_service):
    """Fetch files from Google Drive folders with permissions."""
    service = google_drive_service
    
    # Get all shared resources
    shared_files = list_shared_resources(service, context)
    all_files = []
    total_size = 0
    
    # Process each shared file
    for file in shared_files:
        try:
            # If it's a folder and recursive is enabled, process it recursively
            if file['mimeType'] == 'application/vnd.google-apps.folder' and config.recursive:
                folder_files = fetch_files_recursive(service, file['id'], context, config)
                all_files.extend(folder_files)
            # For files, check if they match the supported file types
            elif any(file['name'].endswith(ext) for ext in config.file_types):
                all_files.append(file)
                total_size += int(file.get('size', 0))
                
        except HttpError as error:
            context.log.error(f"Error processing file {file.get('name', 'unknown')}: {error}")
    
    context.add_output_metadata({
        "num_files": len(all_files),
        "total_size_bytes": total_size,
        "recursive_mode": MetadataValue.text("Enabled" if config.recursive else "Disabled"),
        "preview": MetadataValue.json(all_files[:5] if all_files else [])
    })
    
    return all_files

@asset
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
            is_public = False
            accessible_by_emails = []
            accessible_by_domains = []
            
            for perm in file.get('detailed_permissions', []):
                permission_entry = {
                    "type": perm.get('type'),
                    "role": perm.get('role'),
                }
                
                # Check if file is public
                if perm.get('type') == 'anyone' and perm.get('role') in ['reader', 'writer', 'owner']:
                    is_public = True
                
                # Track email access
                if 'emailAddress' in perm:
                    permission_entry['email'] = perm['emailAddress']
                    accessible_by_emails.append(perm['emailAddress'])
                
                # Track domain access
                if 'domain' in perm:
                    permission_entry['domain'] = perm['domain']
                    accessible_by_domains.append(perm['domain'])
                    
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
                "permissions": permissions,
                "is_public": is_public,
                "accessible_by_emails": accessible_by_emails,
                "accessible_by_domains": accessible_by_domains
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

@asset
def fetch_google_drive_files(context: AssetExecutionContext):
    """Fetch files from Google Drive and store content in Elasticsearch, relationships in Neo4j."""
    service = get_google_drive_service()
    results = service.files().list(
        pageSize=100,
        fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, owners, webViewLink, parents)"
    ).execute()
    items = results.get('files', [])
    
    # Create Elasticsearch index with proper mapping
    if not es.indices.exists(index="google_drive_files"):
        es.indices.create(
            index="google_drive_files",
            mappings={
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {"type": "text", "analyzer": "standard"},
                    "mimeType": {"type": "keyword"},
                    "createdTime": {"type": "date"},
                    "modifiedTime": {"type": "date"},
                    "webViewLink": {"type": "keyword"},
                    "content": {"type": "text", "analyzer": "standard"},
                    "owners": {
                        "type": "nested",
                        "properties": {
                            "emailAddress": {"type": "keyword"},
                            "displayName": {"type": "text"}
                        }
                    }
                }
            }
        )
    
    # Store in Neo4j - only relationships and minimal metadata
    with neo4j_driver.session() as session:
        # Create constraints if they don't exist
        session.run("""
            CREATE CONSTRAINT file_id IF NOT EXISTS
            FOR (f:File) REQUIRE f.id IS UNIQUE
        """)
        session.run("""
            CREATE CONSTRAINT owner_email IF NOT EXISTS
            FOR (o:Owner) REQUIRE o.email IS UNIQUE
        """)
        
        for item in items:
            # Store minimal metadata in Neo4j
            session.run("""
                MERGE (f:File {id: $id})
                SET f.name = $name
                WITH f
                UNWIND $owners as owner
                MERGE (o:Owner {email: owner.emailAddress})
                MERGE (f)-[:OWNED_BY]->(o)
                WITH f, owner
                WHERE $parents IS NOT NULL
                UNWIND $parents as parent_id
                MERGE (p:Folder {id: parent_id})
                MERGE (f)-[:IN_FOLDER]->(p)
            """, **item)
    
    # Store full content in Elasticsearch
    for item in items:
        try:
            # Get file content based on mime type
            if 'google-apps' in item['mimeType']:
                # For Google Docs, export as text
                content = service.files().export(
                    fileId=item['id'],
                    mimeType='text/plain'
                ).execute()
            else:
                # For other files, download content
                content = service.files().get_media(fileId=item['id']).execute()
            
            # Index in Elasticsearch with full content
            es.index(
                index="google_drive_files",
                id=item['id'],
                document={
                    **item,
                    "content": content.decode('utf-8') if isinstance(content, bytes) else content
                }
            )
        except Exception as e:
            context.log.error(f"Error processing file {item['id']}: {e}")
    
    return len(items)

@asset
def process_file_relationships(context: AssetExecutionContext):
    """Process relationships between files based on their content and metadata."""
    with neo4j_driver.session() as session:
        # Find similar files based on content (using Elasticsearch)
        similar_files = es.search(
            index="google_drive_files",
            body={
                "query": {
                    "more_like_this": {
                        "fields": ["content"],
                        "like": [],
                        "min_term_freq": 1,
                        "max_query_terms": 12
                    }
                }
            }
        )
        
        # Store similarity relationships in Neo4j
        for hit in similar_files['hits']['hits']:
            source_id = hit['_id']
            for similar_hit in hit['_source'].get('similar_files', []):
                session.run("""
                    MATCH (f1:File {id: $source_id})
                    MATCH (f2:File {id: $similar_id})
                    MERGE (f1)-[:SIMILAR_TO {score: $score}]->(f2)
                """, {
                    "source_id": source_id,
                    "similar_id": similar_hit['id'],
                    "score": similar_hit['score']
                })
        
        # Count relationships
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) as relationship_type, count(*) as count
        """)
        return {record["relationship_type"]: record["count"] for record in result}

# Define jobs
google_drive_indexing_job = define_asset_job(
    name="google_drive_indexing_job",
    selection=[haystack_indexed_files]
)

# Define schedules
google_drive_schedule = ScheduleDefinition(
    job=google_drive_indexing_job,
    cron_schedule="0 */6 * * *",  # Run every 6 hours
)

# Create definitions object
defs = Definitions(
    assets=[google_drive_service, google_drive_files, haystack_indexed_files, fetch_google_drive_files, process_file_relationships],
    schedules=[google_drive_schedule],
    jobs=[google_drive_indexing_job],
) 