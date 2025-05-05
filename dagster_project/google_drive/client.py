import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

class GoogleDriveClient:
    def __init__(self, credentials_file: str):
        self.credentials_file = credentials_file
        self.service = self._authenticate()

    def _authenticate(self):
        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_file,
            scopes=SCOPES
        )
        return build('drive', 'v3', credentials=credentials)

    def list_files(self, query: str, fields: str = None, page_token: str = None, page_size: int = 100):
        try:
            response = self.service.files().list(
                q=query,
                fields=fields or "nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink)",
                pageToken=page_token,
                pageSize=page_size
            ).execute()
            return response
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None

    def fetch_files_recursive(self, folder_id, context, config, depth=0, max_depth=10, parent_id=None):
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
            folder_info = self.service.files().get(fileId=folder_id, fields="name,id").execute()
            folder_name = folder_info.get("name", folder_id)
            # Track this folder and its parent
            all_folders.append({
                "id": folder_id,
                "name": folder_name,
                "parent_id": parent_id
            })
            context.log.info(f"Processing folder (depth {depth}): {folder_name} ({folder_id})")
            query = f"'{folder_id}' in parents and trashed = false"
            page_token = None
            files_processed = 0
            while True:
                if files_processed >= config.max_files:
                    context.log.info(f"Reached max files limit ({config.max_files}) for folder {folder_name}")
                    break
                context.log.info(f"Querying files in folder {folder_name} (batch {files_processed//100 + 1})")
                response = self.service.files().list(
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
                        sub_result = self.fetch_files_recursive(
                            item['id'],
                            context,
                            config,
                            depth + 1,
                            max_depth,
                            parent_id=folder_id
                        )
                        all_files.extend(sub_result["files"])
                        all_folders.extend(sub_result["folders"])
                        context.log.info(
                            f"Completed processing subfolder {item['name']}, found {len(sub_result['files'])} files and {len(sub_result['folders'])} folders"
                        )
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
                                perms = self.service.permissions().list(
                                    fileId=item['id'],
                                    fields="permissions(id,type,emailAddress,role,domain)"
                                ).execute()
                                item['detailed_permissions'] = perms.get('permissions', [])
                            except Exception as e:
                                context.log.warning(
                                    f"Could not get permissions for {item['name']}, will process with basic permissions: {e}"
                                )
                                item['detailed_permissions'] = [{
                                    'type': 'user',
                                    'role': 'unknown',
                                    'emailAddress': context.run_id if hasattr(context, 'run_id') else 'service_account',
                                    'note': (
                                        'Could not retrieve full permissions; this is a fallback entry.'
                                    )
                                }]
                            # Set parent_id for every file
                            item['parent_id'] = folder_id
                            all_files.append(item)
                            files_processed += 1
                            context.log.info(f"Successfully processed file: {item['name']}")
                        else:
                            context.log.info(
                                f"Skipping unsupported file type: {item['name']} ({mime_type})"
                            )
                page_token = response.get('nextPageToken')
                if not page_token or files_processed >= config.max_files:
                    context.log.info(
                        f"Completed processing folder {folder_name}, found {len(all_files)} files"
                    )
                    break
        except HttpError as error:
            context.log.error(f"Error accessing folder {folder_id}: {error}")
        return {"files": all_files, "folders": all_folders}

    def export_google_doc(self, file_id, export_mime_type="text/plain"):
        try:
            return self.service.files().export(fileId=file_id, mimeType=export_mime_type).execute()
        except HttpError as e:
            print(f"Could not export Google Doc {file_id}: {e}")
            return None

    def download_file(self, file_id):
        try:
            return self.service.files().get_media(fileId=file_id).execute()
        except HttpError as e:
            print(f"Could not download file {file_id}: {e}")
            return None 