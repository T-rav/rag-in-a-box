from dagster import build_op_context
from google_drive_assets import google_drive_service, google_drive_files, index_files, GoogleDriveConfig

def test_assets():
    # Create config
    config = GoogleDriveConfig(
        credentials_file="/app/credentials/credentials.json",
        haystack_api_url="http://haystack:8000",
        file_types=[
            ".txt", ".md", ".pdf", ".docx",  # Regular files
            "application/vnd.google-apps.document",  # Google Docs
            "application/vnd.google-apps.spreadsheet",  # Google Sheets
            "application/vnd.google-apps.presentation"  # Google Slides
        ],
        max_files=1000,
        recursive=True
    )
    
    # Test the assets in sequence
    print("Testing google_drive_service...")
    service = google_drive_service(build_op_context(), config)
    print("Service created successfully")
    
    print("\nTesting google_drive_files...")
    files = google_drive_files(build_op_context(), config, service)
    print(f"Found {len(files)} files")
    
    print("\nTesting index_files...")
    result = index_files(build_op_context(), config, files, service)
    print(f"Indexing result: {result}")

if __name__ == "__main__":
    test_assets() 