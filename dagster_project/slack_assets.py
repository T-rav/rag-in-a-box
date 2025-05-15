import os
import logging
from typing import Dict, Any, List
import pandas as pd
from dagster import asset, AssetExecutionContext, MetadataValue, Config, Definitions, ScheduleDefinition, define_asset_job

from slack.client import SlackClient
from slack.scraper import SlackScraper
from slack.utils import format_slack_message, format_slack_channel, format_slack_user
from slack.neo4j_service import SlackNeo4jService
from slack.elastic_service import SlackElasticsearchService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SlackConfig(Config):
    """Configuration for Slack scraping."""
    max_messages_per_channel: int = 1000
    include_threads: bool = True
    include_reactions: bool = True
    include_files: bool = True
    include_canvases: bool = True
    include_links: bool = True
    max_recursion_depth: int = 5

@asset
def slack_users(context: AssetExecutionContext) -> pd.DataFrame:
    """Get all Slack users and their information."""
    client = SlackClient()
    try:
        users = client.get_users()
        user_emails = client.get_user_emails()
        context.log.info(f"Found {len(users)} users, {len(user_emails)} with emails")
        
        # Store user info in Neo4j and Elasticsearch
        neo4j_service = SlackNeo4jService()
        es_service = SlackElasticsearchService()
        
        for user in users:
            formatted_user = format_slack_user(user)
            neo4j_service.create_or_update_user(formatted_user)
            es_service.index_user(formatted_user)
        
        # Create DataFrame for user emails
        df = pd.DataFrame(user_emails)
        context.add_output_metadata({
            "num_users": len(users),
            "num_users_with_email": len(user_emails),
            "preview": MetadataValue.json(df.head().to_dict(orient="records"))
        })
        return df
    except Exception as e:
        context.log.error(f"Error getting user info: {e}")
        raise

@asset
def slack_channel_info(context: AssetExecutionContext) -> Dict[str, Any]:
    """Get information about all Slack channels."""
    client = SlackClient()
    try:
        channels = client.get_public_channels()
        context.log.info(f"Found {len(channels)} public channels")
        
        # Store channel info in Neo4j and Elasticsearch
        neo4j_service = SlackNeo4jService()
        es_service = SlackElasticsearchService()
        
        for channel in channels:
            formatted_channel = format_slack_channel(channel)
            neo4j_service.create_or_update_channel(formatted_channel)
            es_service.index_channel(formatted_channel)
        
        context.add_output_metadata({
            "num_channels": len(channels),
            "channel_names": MetadataValue.json([c["name"] for c in channels[:5]])
        })
        return {"channels": channels}
    except Exception as e:
        context.log.error(f"Error getting channel info: {e}")
        raise

@asset
def scrape_slack_content(context: AssetExecutionContext, config: SlackConfig) -> Dict[str, Any]:
    """Scrape Slack content including messages, reactions, and files."""
    client = SlackClient()
    scraper = SlackScraper(client)
    try:
        # Get all public channels
        channels = client.get_public_channels()
        context.log.info(f"Found {len(channels)} channels to scrape")
        
        # Scrape each channel
        results = []
        for channel in channels:
            try:
                result = scraper.scrape_channel(channel, config.dict())
                results.append(result)
                context.log.info(
                    f"Scraped channel {channel['name']}: "
                    f"{result['message_count']} messages, "
                    f"{result['pin_count']} pins, "
                    f"{result['bookmark_count']} bookmarks"
                )
            except Exception as e:
                context.log.error(f"Error scraping channel {channel['name']}: {e}")
                continue
        
        # Aggregate results
        total_messages = sum(r["message_count"] for r in results)
        total_pins = sum(r["pin_count"] for r in results)
        total_bookmarks = sum(r["bookmark_count"] for r in results)
        
        context.add_output_metadata({
            "channels_scraped": len(results),
            "total_messages": total_messages,
            "total_pins": total_pins,
            "total_bookmarks": total_bookmarks,
            "preview": MetadataValue.json(results[:5])
        })
        
        return {
            "channels_scraped": len(results),
            "total_messages": total_messages,
            "total_pins": total_pins,
            "total_bookmarks": total_bookmarks,
            "results": results
        }
    except Exception as e:
        context.log.error(f"Error scraping Slack content: {e}")
        raise

# Define two simple jobs 
slack_users_job = define_asset_job(
    name="slack_users_job",
    selection=[slack_users]
)

slack_channels_job = define_asset_job(
    name="slack_channels_job",
    selection=[slack_channel_info, scrape_slack_content]
)

# Define schedules
slack_users_schedule = ScheduleDefinition(
    job=slack_users_job,
    cron_schedule="0 0 * * *",  # Run once a day
)

slack_channels_schedule = ScheduleDefinition(
    job=slack_channels_job,
    cron_schedule="0 */6 * * *",  # Run every 6 hours
)

# Create definitions object
defs = Definitions(
    assets=[slack_users, slack_channel_info, scrape_slack_content],
    schedules=[slack_users_schedule, slack_channels_schedule],
    jobs=[slack_users_job, slack_channels_job],
)
