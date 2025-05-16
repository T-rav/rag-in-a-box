from dagster import build_op_context
from .google_drive_assets import (
    google_drive_service,
    google_drive_files,
    index_files,
    GoogleDriveConfig,
)
import os
from dotenv import load_dotenv
import logging
import unittest.mock as mock
import pytest

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from parent directory's .env file
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

# Override Neo4j and Elasticsearch hostnames for testing
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["ELASTICSEARCH_HOST"] = "localhost"


@mock.patch('dagster_project.google_drive_assets.service_account')
@mock.patch('dagster_project.google_drive_assets.build')
def test_google_drive_service_mocked(mock_build, mock_service_account):
    # Mock the Google Drive API service
    mock_service = mock.MagicMock()
    mock_build.return_value = mock_service
    
    # Mock the credentials
    mock_credentials = mock.MagicMock()
    mock_service_account.Credentials.from_service_account_file.return_value = mock_credentials
    
    # Create config with a non-existent file, it will be mocked anyway
    config = GoogleDriveConfig(
        credentials_file="mock_credentials.json",
        haystack_api_url="http://localhost:8000",
        file_types=[
            ".txt",
            ".md",
            ".pdf",
            ".docx",
            "application/vnd.google-apps.document",
            "application/vnd.google-apps.spreadsheet",
            "application/vnd.google-apps.presentation",
        ],
        max_files=10,
        recursive=True,
    )
    
    # Mock about API call
    mock_about = mock.MagicMock()
    mock_service.about().get().execute.return_value = {"user": {"emailAddress": "mock@example.com"}}
    
    # Test the service creation
    service = google_drive_service(build_op_context(), config)
    
    # Verify service was created
    assert service is not None
    assert service == mock_service
    
    # Verify the credentials file was used
    mock_service_account.Credentials.from_service_account_file.assert_called_once()


@mock.patch('dagster_project.google_drive.client.GoogleDriveClient._authenticate')
def test_google_drive_files_mocked(mock_authenticate):
    # Mock the authentication and service
    mock_service = mock.MagicMock()
    mock_authenticate.return_value = mock_service
    
    # Mock the files API response
    mock_files_list = mock.MagicMock()
    mock_files_response = {
        "files": [
            {
                "id": "file1",
                "name": "Test File 1",
                "mimeType": "text/plain",
                "webViewLink": "https://example.com/1"
            },
            {
                "id": "file2",
                "name": "Test File 2",
                "mimeType": "application/pdf",
                "webViewLink": "https://example.com/2"
            }
        ]
    }
    mock_files_list.execute.return_value = mock_files_response
    mock_service.files().list.return_value = mock_files_list
    
    # Create config
    config = GoogleDriveConfig(
        credentials_file="mock_credentials.json",
        haystack_api_url="http://localhost:8000",
        file_types=[".txt", ".pdf"],
        max_files=10,
        recursive=True,
    )
    
    # Test the files asset
    files = google_drive_files(build_op_context(), config)
    
    # Verify results
    assert files is not None


@mock.patch('dagster_project.google_drive.client.GoogleDriveClient._authenticate')
@mock.patch('dagster_project.google_drive_assets.ElasticsearchService')
@mock.patch('dagster_project.google_drive_assets.Neo4jService')
def test_index_files_mocked(mock_neo4j_service_class, mock_es_service_class, mock_authenticate):
    # Mock the authentication and service
    mock_service = mock.MagicMock()
    mock_authenticate.return_value = mock_service
    
    # Mock Neo4j service
    mock_neo4j_service = mock.MagicMock()
    mock_neo4j_service_class.return_value = mock_neo4j_service
    
    # Mock Elasticsearch service
    mock_es_service = mock.MagicMock()
    mock_es_service_class.return_value = mock_es_service
    
    # Create sample files - need to provide as dict since that's what the function expects
    files = {
        "files": [
            {
                "id": "file1",
                "name": "Test File 1",
                "mimeType": "text/plain",
                "webViewLink": "https://example.com/1",
                "content": "This is a test file content"
            }
        ],
        "folders": [
            {
                "id": "folder1",
                "name": "Test Folder",
                "parent_id": None
            }
        ]
    }
    
    # Create config
    config = GoogleDriveConfig(
        credentials_file="mock_credentials.json",
        haystack_api_url="http://localhost:8000",
        file_types=[".txt", ".pdf"],
        max_files=10,
        recursive=True,
    )
    
    # Test the index_files asset
    result = index_files(build_op_context(), config, files)
    
    # Verify results
    assert result is not None
    
    # Verify services were created and methods were called
    mock_neo4j_service_class.assert_called_once()
    mock_es_service_class.assert_called_once()
    
    # Verify folder creation was called
    mock_neo4j_service.create_or_update_folder.assert_called_with(
        "folder1", "Test Folder", None
    )


def test_google_drive_assets():
    """Run all tests in sequence with proper mocking"""
    try:
        logger.info("Testing google_drive_service with mocks...")
        test_google_drive_service_mocked()
        
        logger.info("Testing google_drive_files with mocks...")
        test_google_drive_files_mocked()
        
        logger.info("Testing index_files with mocks...")
        test_index_files_mocked()
        
        logger.info("All tests passed!")
    except Exception as e:
        logger.error(f"Error in Google Drive test: {str(e)}")
        raise


if __name__ == "__main__":
    try:
        logger.info("Testing Google Drive assets...")
        test_google_drive_assets()
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise
