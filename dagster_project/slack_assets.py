from dagster import asset, AssetExecutionContext, MetadataValue
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
from typing import Optional, Dict, Any, List
import pandas as pd
from sqlalchemy import create_engine, Table, Column, String, MetaData
from sqlalchemy.dialects.postgresql import JSONB

class SlackClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        if not self.token:
            raise ValueError("Slack bot token not found. Please set SLACK_BOT_TOKEN environment variable or pass token directly.")
        self.client = WebClient(token=self.token)

    def send_message(self, channel: str, text: str, blocks: Optional[list] = None) -> Dict[str, Any]:
        """Send a message to a Slack channel."""
        try:
            response = self.client.chat_postMessage(
                channel=channel,
                text=text,
                blocks=blocks
            )
            return response.data
        except SlackApiError as e:
            print(f"Error sending message: {e.response['error']}")
            raise

    def get_channel_info(self, channel: str) -> Dict[str, Any]:
        """Get information about a Slack channel."""
        try:
            response = self.client.conversations_info(channel=channel)
            return response.data
        except SlackApiError as e:
            print(f"Error getting channel info: {e.response['error']}")
            raise

    def get_users(self) -> List[Dict[str, Any]]:
        """Get all users from the Slack workspace."""
        try:
            users = []
            cursor = None
            
            while True:
                response = self.client.users_list(cursor=cursor)
                users.extend(response['members'])
                
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
            
            return users
        except SlackApiError as e:
            print(f"Error getting users: {e.response['error']}")
            raise

    def get_user_emails(self) -> List[Dict[str, str]]:
        """Get user emails from the Slack workspace."""
        users = self.get_users()
        user_emails = []
        
        for user in users:
            if not user.get('deleted') and user.get('profile', {}).get('email'):
                user_emails.append({
                    'slack_id': user['id'],
                    'slack_username': user['name'],
                    'email': user['profile']['email'],
                    'real_name': user['profile'].get('real_name', ''),
                    'display_name': user['profile'].get('display_name', '')
                })
        
        return user_emails

@asset
def slack_test_message(context: AssetExecutionContext) -> str:
    """Test asset that sends a message to a configured Slack channel."""
    client = SlackClient()
    channel = os.getenv("SLACK_CHANNEL", "#general")
    
    message = "Hello from Dagster! This is a test message from the Slack integration."
    response = client.send_message(channel=channel, text=message)
    
    context.log.info(f"Message sent to {channel}: {response}")
    return f"Message sent to {channel}"

@asset
def slack_channel_info(context: AssetExecutionContext) -> Dict[str, Any]:
    """Asset that retrieves information about the configured Slack channel."""
    client = SlackClient()
    channel = os.getenv("SLACK_CHANNEL", "#general")
    
    info = client.get_channel_info(channel=channel)
    context.log.info(f"Channel info for {channel}: {info}")
    return info

@asset
def slack_users(context: AssetExecutionContext) -> pd.DataFrame:
    """Asset that retrieves all users from Slack and stores them in PostgreSQL."""
    client = SlackClient()
    
    # Get users and their emails
    user_emails = client.get_user_emails()
    
    # Convert to DataFrame
    df = pd.DataFrame(user_emails)
    
    # Store in PostgreSQL
    engine = create_engine(os.getenv("POSTGRES_CONN_STRING"))
    metadata = MetaData()
    
    # Define the table
    users_table = Table(
        'slack_users',
        metadata,
        Column('slack_id', String, primary_key=True),
        Column('slack_username', String),
        Column('email', String),
        Column('real_name', String),
        Column('display_name', String),
        Column('raw_data', JSONB)
    )
    
    # Create table if it doesn't exist
    metadata.create_all(engine)
    
    # Store the data
    df.to_sql('slack_users', engine, if_exists='replace', index=False)
    
    # Add metadata
    context.add_output_metadata({
        "num_users": MetadataValue.int(len(df)),
        "preview": MetadataValue.md(df.head().to_markdown())
    })
    
    return df 