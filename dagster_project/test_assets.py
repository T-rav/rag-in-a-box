from dagster import build_op_context
from google_drive_assets import (
    google_drive_service,
    google_drive_files,
    index_files,
    GoogleDriveConfig,
)
from slack_assets import SlackClient, SlackConfig
import os
from dotenv import load_dotenv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from parent directory's .env file
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

# Override Neo4j and Elasticsearch hostnames for local testing
os.environ["NEO4J_URI"] = "bolt://localhost:7687"
os.environ["ELASTICSEARCH_HOST"] = "localhost"


def test_google_drive_assets():
    try:
        # Create config
        config = GoogleDriveConfig(
            credentials_file=os.path.join(
                os.path.dirname(__file__), "..", "credentials", "credentials.json"
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
        files = google_drive_files(build_op_context(), config, service)
        logger.info(f"Found {len(files)} files")

        logger.info("Testing index_files...")
        try:
            result = index_files(build_op_context(), config, files, service)
            logger.info(f"Indexing result: {result}")
        except Exception as e:
            logger.error(f"Error during indexing: {str(e)}")
            logger.error("Make sure Neo4j and Elasticsearch are running and accessible")
            raise

    except Exception as e:
        logger.error(f"Error in Google Drive test: {str(e)}")
        raise


def test_slack_assets():
    try:
        # Create config
        config = SlackConfig(
            max_messages_per_channel=10,  # Limit for testing
            include_threads=True,
            include_reactions=True,
            include_files=True,
            include_canvases=True,
            include_links=True,
        )

        # Initialize Slack client
        logger.info("Testing Slack client initialization...")
        client = SlackClient()
        logger.info("Client created successfully")

        # Test getting users
        logger.info("Testing user retrieval...")
        users = client.get_users()
        logger.info(f"Found {len(users)} users")

        # Test getting user emails
        logger.info("Testing user email retrieval...")
        user_emails = client.get_user_emails()
        logger.info(f"Found {len(user_emails)} user emails")

        # Test getting public channels
        logger.info("Testing public channel retrieval...")
        channels = client.get_public_channels()
        logger.info(f"Found {len(channels)} public channels")

        # Test scraping a few channels
        test_channels = channels[:2]  # Test with first 2 channels
        for channel in test_channels:
            logger.info(f"\nTesting channel: {channel['name']}")

            try:
                # Test channel info
                channel_info = client.get_channel_info(channel=channel["id"])
                logger.info(f"Channel info: {channel_info}")

                # Test getting channel messages
                messages = client.get_channel_messages(channel["id"], config=config)
                logger.info(f"Found {len(messages)} messages in channel")

                # Test getting channel pins
                pins = client.get_channel_pins(channel["id"])
                logger.info(f"Found {len(pins)} pins in channel")

                # Test getting channel bookmarks
                bookmarks = client.get_channel_bookmarks(channel["id"])
                logger.info(f"Found {len(bookmarks)} bookmarks in channel")

                # Test getting channel permissions
                permissions = client.get_channel_permissions(channel["id"])
                logger.info(f"Channel permissions: {permissions}")

                # Test storing data
                try:
                    client.store_channel_data(
                        channel_id=channel["id"],
                        channel_info=channel_info,
                        messages=messages,
                        pins=pins,
                        bookmarks=bookmarks,
                        permissions=permissions,
                    )
                    logger.info(f"Successfully stored data for channel {channel['name']}")
                except Exception as e:
                    logger.error(f"Error storing data for channel {channel['name']}: {str(e)}")
                    logger.error("Make sure Neo4j and Elasticsearch are running and accessible")
                    raise

            except Exception as e:
                logger.error(f"Error processing channel {channel['name']}: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Error in Slack test: {str(e)}")
        raise


if __name__ == "__main__":
    try:
        logger.info("Testing Google Drive assets...")
        test_google_drive_assets()

        logger.info("\nTesting Slack assets...")
        test_slack_assets()
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        raise
