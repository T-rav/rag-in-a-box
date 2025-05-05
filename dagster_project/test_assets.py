from dagster import build_op_context
from google_drive_assets import (
    google_drive_service,
    google_drive_files,
    index_files,
    GoogleDriveConfig,
)
import os
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from parent directory's .env file
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

# Override Neo4j and Elasticsearch hostnames for Docker
os.environ["NEO4J_URI"] = "bolt://neo4j:7687"
os.environ["ELASTICSEARCH_HOST"] = "elasticsearch"


def test_google_drive_assets():
    try:
        # Create config
        config = GoogleDriveConfig(
            credentials_file=os.path.join(
                os.path.dirname(__file__), "credentials", "credentials.json"
            ),
            haystack_api_url="http://localhost:8000",  # Use localhost for testing
            file_types=[
                ".txt",
                ".md",
                ".pdf",
                ".docx",  # Regular files
                "application/vnd.google-apps.document",  # Google Docs
                "application/vnd.google-apps.spreadsheet",  # Google Sheets
                "application/vnd.google-apps.presentation",  # Google Slides
            ],
            max_files=1000,
            recursive=True,
        )

        # Test the assets in sequence
        logger.info("Testing google_drive_service...")
        service = google_drive_service(build_op_context(), config)
        logger.info("Service created successfully")

        logger.info("Testing google_drive_files...")
        files = google_drive_files(build_op_context(), config)
        logger.info(f"Found {len(files)} files")

        logger.info("Testing index_files...")
        try:
            result = index_files(build_op_context(), config, files)
            logger.info(f"Indexing result: {result}")
        except Exception as e:
            logger.error(f"Error during indexing: {str(e)}")
            logger.error("Make sure Neo4j and Elasticsearch are running and accessible")
            raise

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
