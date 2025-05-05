from dagster import asset, AssetExecutionContext, MetadataValue, Config
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import os
from typing import Optional, Dict, Any, List
import pandas as pd
from sqlalchemy import create_engine, MetaData
from neo4j import GraphDatabase
from elasticsearch import Elasticsearch
import json
import hashlib
import logging
import re
from urllib.parse import urlparse
import time

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


class SlackClient:
    def __init__(self, token: Optional[str] = None, rate_limit_delay: float = 1.0):
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        if not self.token:
            raise ValueError(
                "Slack bot token not found. Please set SLACK_BOT_TOKEN environment variable or pass token directly."
            )
        self.client = WebClient(token=self.token)
        self.logger = logging.getLogger(__name__)
        self.rate_limit_delay = rate_limit_delay

    def _to_dict(self, obj):
        """Convert a Slack response object to a dictionary."""
        if hasattr(obj, "data"):
            return obj.data
        elif isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._to_dict(item) for item in obj]
        return obj

    def _flatten_dict(
        self, d: Dict[str, Any], parent_key: str = "", sep: str = "_"
    ) -> Dict[str, Any]:
        """Flatten a nested dictionary by concatenating keys with a separator."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert list to string representation
                items.append((new_key, json.dumps(v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def _handle_rate_limit(self, e: SlackApiError) -> None:
        """Handle rate limiting by waiting and retrying."""
        if e.response["error"] == "ratelimited":
            retry_after = int(e.response.headers.get("Retry-After", self.rate_limit_delay))
            self.logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            return True
        return False

    def _make_slack_call(self, call_func, *args, **kwargs):
        """Make a Slack API call with rate limit handling."""
        max_retries = 3
        current_retry = 0

        while current_retry < max_retries:
            try:
                response = call_func(*args, **kwargs)
                time.sleep(self.rate_limit_delay)  # Add delay between calls
                return response
            except SlackApiError as e:
                if self._handle_rate_limit(e):
                    current_retry += 1
                    continue
                raise

        raise SlackApiError("Max retries exceeded for rate limiting", None)

    def send_message(
        self, channel: str, text: str, blocks: Optional[list] = None
    ) -> Dict[str, Any]:
        """Send a message to a Slack channel."""
        return self._make_slack_call(
            self.client.chat_postMessage, channel=channel, text=text, blocks=blocks
        )

    def get_channel_info(self, channel: str) -> Dict[str, Any]:
        """Get information about a Slack channel."""
        return self._make_slack_call(self.client.conversations_info, channel=channel)

    def get_users(self) -> List[Dict[str, Any]]:
        """Get all users from the Slack workspace."""
        users = []
        cursor = None

        while True:
            response = self._make_slack_call(self.client.users_list, cursor=cursor)
            users.extend(response["members"])

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        return users

    def get_user_emails(self) -> List[Dict[str, str]]:
        """Get user emails from the Slack workspace."""
        users = self.get_users()
        user_emails = []

        for user in users:
            if not user.get("deleted") and user.get("profile", {}).get("email"):
                user_emails.append(
                    {
                        "slack_id": user["id"],
                        "slack_username": user["name"],
                        "email": user["profile"]["email"],
                        "real_name": user["profile"].get("real_name", ""),
                        "display_name": user["profile"].get("display_name", ""),
                    }
                )

        return user_emails

    def get_public_channels(self) -> List[Dict[str, Any]]:
        """Get all public channels in the workspace."""
        channels = []
        cursor = None

        while True:
            self.logger.info(f"Fetching channels batch (cursor: {cursor})")
            response = self._make_slack_call(
                self.client.conversations_list, types="public_channel", cursor=cursor, limit=1000
            )
            channels.extend(response["channels"])
            self.logger.info(f"Found {len(response['channels'])} channels in this batch")

            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

        self.logger.info(f"Total public channels found: {len(channels)}")
        return channels

    def get_channel_messages(
        self, channel_id: str, oldest: Optional[str] = None, config: Optional[SlackConfig] = None
    ) -> List[Dict[str, Any]]:
        """Get messages from a channel with reactions and metadata."""
        try:
            # Join the channel if not already a member
            try:
                self._make_slack_call(self.client.conversations_join, channel=channel_id)
                self.logger.info(f"Joined channel {channel_id}")
            except SlackApiError as e:
                if e.response["error"] != "already_in_channel":
                    raise

            messages = []
            cursor = None
            messages_processed = 0

            while True:
                if config and messages_processed >= config.max_messages_per_channel:
                    self.logger.info(
                        f"Reached max messages limit ({config.max_messages_per_channel}) for channel {channel_id}"
                    )
                    break

                self.logger.info(
                    f"Fetching messages batch for channel {channel_id} (cursor: {cursor})"
                )
                response = self._make_slack_call(
                    self.client.conversations_history,
                    channel=channel_id,
                    cursor=cursor,
                    limit=(
                        min(100, config.max_messages_per_channel - messages_processed)
                        if config
                        else 100
                    ),
                    oldest=oldest,
                    include_all_metadata=True,
                )
                batch_messages = response["messages"]
                self.logger.info(f"Found {len(batch_messages)} messages in this batch")

                for message in batch_messages:
                    # Get message reactions if enabled
                    if config and config.include_reactions:
                        try:
                            reactions = self._make_slack_call(
                                self.client.reactions_get,
                                channel=channel_id,
                                timestamp=message["ts"],
                            )
                            message["reactions"] = reactions.get("message", {}).get("reactions", [])
                        except SlackApiError as e:
                            self.logger.warning(
                                f"Could not get reactions for message {message['ts']}: {e}"
                            )
                            message["reactions"] = []

                    # Get thread replies if enabled
                    if config and config.include_threads and message.get("thread_ts"):
                        try:
                            thread = self._make_slack_call(
                                self.client.conversations_replies,
                                channel=channel_id,
                                ts=message["thread_ts"],
                            )
                            message["thread_replies"] = thread.get("messages", [])
                        except SlackApiError as e:
                            self.logger.warning(
                                f"Could not get thread replies for message {message['ts']}: {e}"
                            )
                            message["thread_replies"] = []

                    # Extract links if enabled
                    if config and config.include_links:
                        message["links"] = self._extract_links(message.get("text", ""))

                messages.extend(batch_messages)
                messages_processed += len(batch_messages)

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            self.logger.info(f"Total messages processed for channel {channel_id}: {len(messages)}")
            return messages
        except SlackApiError as e:
            self.logger.error(f"Error getting messages: {e.response['error']}")
            raise

    def _extract_links(self, text: str) -> List[Dict[str, str]]:
        """Extract and validate links from message text."""
        links = []
        # Match URLs in text
        url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        for url in re.findall(url_pattern, text):
            try:
                parsed = urlparse(url)
                if parsed.scheme or parsed.netloc:
                    links.append(
                        {"url": url, "domain": parsed.netloc, "path": parsed.path, "is_valid": True}
                    )
            except Exception as e:
                self.logger.warning(f"Error parsing URL {url}: {e}")
        return links

    def get_channel_pins(self, channel_id: str) -> List[Dict[str, Any]]:
        """Get pinned items from a channel with full content."""
        try:
            response = self._make_slack_call(self.client.pins_list, channel=channel_id)
            pins = []

            for item in response["items"]:
                pin_data = {
                    "id": item["id"],
                    "type": item["type"],
                    "channel": channel_id,
                    "timestamp": item.get("created", None),
                    "created_by": item.get("created_by", None),
                }

                # Get full content based on type
                if item["type"] == "message":
                    try:
                        message = self._make_slack_call(
                            self.client.conversations_history,
                            channel=channel_id,
                            latest=item["message"]["ts"],
                            limit=1,
                            inclusive=True,
                        )
                        if message["messages"]:
                            pin_data["content"] = message["messages"][0]
                    except SlackApiError as e:
                        self.logger.warning(f"Could not get pinned message content: {e}")

                elif item["type"] == "file":
                    try:
                        file_info = self._make_slack_call(
                            self.client.files_info, file=item["file"]["id"]
                        )
                        pin_data["content"] = file_info["file"]
                    except SlackApiError as e:
                        self.logger.warning(f"Could not get pinned file content: {e}")

                pins.append(pin_data)

            return pins
        except SlackApiError as e:
            self.logger.error(f"Error getting pins: {e.response['error']}")
            raise

    def get_channel_bookmarks(self, channel_id: str) -> List[Dict[str, Any]]:
        """Get bookmarks from a channel with full content."""
        try:
            response = self._make_slack_call(self.client.bookmarks_list, channel_id=channel_id)
            bookmarks = []

            for bookmark in response["bookmarks"]:
                bookmark_data = {
                    "id": bookmark["id"],
                    "title": bookmark.get("title", ""),
                    "link": bookmark.get("link", ""),
                    "channel": channel_id,
                    "created_by": bookmark.get("created_by", ""),
                    "timestamp": bookmark.get("created", None),
                    "type": bookmark.get("type", "link"),
                    "emoji": bookmark.get("emoji", None),
                    "entity_id": bookmark.get("entity_id", None),
                }

                # Get full content based on type
                if bookmark.get("type") == "message":
                    try:
                        message = self._make_slack_call(
                            self.client.conversations_history,
                            channel=channel_id,
                            latest=bookmark["entity_id"],
                            limit=1,
                            inclusive=True,
                        )
                        if message["messages"]:
                            bookmark_data["content"] = message["messages"][0]
                    except SlackApiError as e:
                        self.logger.warning(f"Could not get bookmarked message content: {e}")

                elif bookmark.get("type") == "file":
                    try:
                        file_info = self._make_slack_call(
                            self.client.files_info, file=bookmark["entity_id"]
                        )
                        bookmark_data["content"] = file_info["file"]
                    except SlackApiError as e:
                        self.logger.warning(f"Could not get bookmarked file content: {e}")

                bookmarks.append(bookmark_data)

            return bookmarks
        except SlackApiError as e:
            self.logger.error(f"Error getting bookmarks: {e.response['error']}")
            raise

    def get_canvas_content(self, canvas_id: str) -> Dict[str, Any]:
        """Get content of a Slack canvas with detailed metadata."""
        try:
            response = self._make_slack_call(self.client.canvases_read, canvas_id=canvas_id)
            canvas = response["canvas"]

            # Get canvas comments if any
            try:
                comments = self._make_slack_call(
                    self.client.canvases_comments_list, canvas_id=canvas_id
                )
                canvas["comments"] = comments.get("comments", [])
            except SlackApiError:
                canvas["comments"] = []

            return canvas
        except SlackApiError as e:
            self.logger.error(f"Error getting canvas: {e.response['error']}")
            raise

    def get_file_info(self, file_id: str) -> Dict[str, Any]:
        """Get detailed information about a shared file."""
        try:
            response = self._make_slack_call(self.client.files_info, file=file_id)
            file_info = response["file"]

            # Get file comments if any
            try:
                comments = self._make_slack_call(self.client.files_comments_list, file=file_id)
                file_info["comments"] = comments.get("comments", [])
            except SlackApiError:
                file_info["comments"] = []

            return file_info
        except SlackApiError as e:
            self.logger.error(f"Error getting file info: {e.response['error']}")
            raise

    def get_channel_permissions(self, channel_id: str) -> Dict[str, Any]:
        """Get detailed permissions and access information for a channel."""
        try:
            # Get channel info with all available fields
            channel_info = self._make_slack_call(
                self.client.conversations_info, channel=channel_id, include_num_members=True
            ).get("channel", {})

            # Get channel members
            members = []
            cursor = None
            while True:
                response = self._make_slack_call(
                    self.client.conversations_members, channel=channel_id, cursor=cursor, limit=1000
                )
                members.extend(response["members"])
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            return {
                "channel_id": channel_id,
                "name": channel_info.get("name"),
                "is_private": channel_info.get("is_private", False),
                "is_archived": channel_info.get("is_archived", False),
                "member_count": channel_info.get("num_members", 0),
                "members": members,
                "created": channel_info.get("created"),
                "creator": channel_info.get("creator"),
                "topic": channel_info.get("topic", {}).get("value"),
                "purpose": channel_info.get("purpose", {}).get("value"),
            }
        except SlackApiError as e:
            self.logger.error(f"Error getting channel permissions: {e.response['error']}")
            raise

    def store_channel_data(
        self,
        channel_id: str,
        channel_info: Dict[str, Any],
        messages: List[Dict[str, Any]],
        pins: List[Dict[str, Any]],
        bookmarks: List[Dict[str, Any]],
        permissions: Dict[str, Any],
    ):
        """Store channel data in Neo4j and Elasticsearch."""
        try:
            # Initialize connections
            neo4j_driver = GraphDatabase.driver(
                os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
            )
            es = Elasticsearch(
                [
                    {
                        "scheme": "http",
                        "host": os.getenv("ELASTICSEARCH_HOST", "localhost"),
                        "port": int(os.getenv("ELASTICSEARCH_PORT", "9200")),
                    }
                ]
            )

            # Convert all data to dictionaries
            channel_info = self._to_dict(channel_info)
            messages = self._to_dict(messages)
            pins = self._to_dict(pins)
            bookmarks = self._to_dict(bookmarks)
            permissions = self._to_dict(permissions)

            # Flatten nested dictionaries for Neo4j
            flattened_channel_info = self._flatten_dict(channel_info)
            flattened_messages = [self._flatten_dict(m) for m in messages]
            flattened_pins = [self._flatten_dict(p) for p in pins]
            flattened_bookmarks = [self._flatten_dict(b) for b in bookmarks]
            self._flatten_dict(permissions)

            # Store in Neo4j
            with neo4j_driver.session() as session:
                # Store channel info
                session.run(
                    """
                    MERGE (c:Channel {id: $id})
                    SET c += $properties
                    """,
                    id=channel_id,
                    properties=flattened_channel_info,
                )

                # Store messages
                for message in flattened_messages:
                    session.run(
                        """
                        MERGE (m:Message {id: $message_id})
                        SET m += $properties
                        WITH m
                        MATCH (c:Channel {id: $channel_id})
                        MERGE (m)-[:IN_CHANNEL]->(c)
                        """,
                        message_id=message["ts"],
                        properties=message,
                        channel_id=channel_id,
                    )

                # Store pins
                for pin in flattened_pins:
                    session.run(
                        """
                        MERGE (p:Pin {id: $pin_id})
                        SET p += $properties
                        WITH p
                        MATCH (c:Channel {id: $channel_id})
                        MERGE (p)-[:IN_CHANNEL]->(c)
                        """,
                        pin_id=pin["id"],
                        properties=pin,
                        channel_id=channel_id,
                    )

                # Store bookmarks
                for bookmark in flattened_bookmarks:
                    session.run(
                        """
                        MERGE (b:Bookmark {id: $bookmark_id})
                        SET b += $properties
                        WITH b
                        MATCH (c:Channel {id: $channel_id})
                        MERGE (b)-[:IN_CHANNEL]->(c)
                        """,
                        bookmark_id=bookmark["id"],
                        properties=bookmark,
                        channel_id=channel_id,
                    )

            # Store in Elasticsearch (can handle nested structures)
            es.index(
                index="slack_channels",
                id=channel_id,
                document={
                    "info": channel_info,
                    "messages": messages,
                    "pins": pins,
                    "bookmarks": bookmarks,
                    "permissions": permissions,
                },
            )

            self.logger.info(f"Successfully stored data for channel {channel_id}")
        except Exception as e:
            self.logger.error(f"Error storing channel data: {e}")
            raise


class SlackScraper:
    def __init__(self, slack_client: SlackClient):
        self.slack = slack_client
        self.neo4j_driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
        )
        self.es = Elasticsearch(
            [
                {
                    "scheme": "http",
                    "host": os.getenv("ELASTICSEARCH_HOST", "localhost"),
                    "port": int(os.getenv("ELASTICSEARCH_PORT", "9200")),
                }
            ]
        )
        self.logger = logging.getLogger(__name__)

    def _to_dict(self, obj):
        """Convert a Slack response object to a dictionary."""
        if hasattr(obj, "data"):
            return obj.data
        elif isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._to_dict(item) for item in obj]
        return obj

    def _generate_document_id(self, source: str, id: str) -> str:
        """Generate a unique document ID for Elasticsearch."""
        return hashlib.md5(f"{source}_{id}".encode()).hexdigest()

    def _store_in_neo4j(
        self,
        data: Dict[str, Any],
        node_type: str,
        relationships: Optional[List[Dict[str, Any]]] = None,
    ):
        """Store data in Neo4j with detailed logging and relationships."""
        try:
            # Convert data to dictionary if it's a Slack response
            data = self._to_dict(data)

            with self.neo4j_driver.session() as session:
                # Create or update node
                query = f"""
                MERGE (n:{node_type} {{id: $id}})
                SET n += $properties
                """
                result = session.run(query, id=data["id"], properties=data)
                self.logger.info(f"Stored {node_type} node with ID {data['id']}")

                # Create relationships if specified
                if relationships:
                    for rel in relationships:
                        rel_query = f"""
                        MATCH (source:{rel['source_type']} {{id: $source_id}})
                        MATCH (target:{rel['target_type']} {{id: $target_id}})
                        MERGE (source)-[r:{rel['type']}]->(target)
                        SET r += $properties
                        """
                        session.run(
                            rel_query,
                            source_id=rel["source_id"],
                            target_id=rel["target_id"],
                            properties=rel.get("properties", {}),
                        )
                        self.logger.info(
                            f"Created relationship {rel['type']} between {rel['source_type']} {rel['source_id']} and {rel['target_type']} {rel['target_id']}"
                        )

                return result
        except Exception as e:
            self.logger.error(f"Error storing {node_type} in Neo4j: {e}")
            raise

    def _store_in_elasticsearch(self, data: Dict[str, Any], index: str):
        """Store data in Elasticsearch with detailed logging."""
        try:
            # Convert data to dictionary if it's a Slack response
            data = self._to_dict(data)

            doc_id = self._generate_document_id(index, data["id"])
            result = self.es.index(index=index, id=doc_id, document=data)
            self.logger.info(f"Stored document in {index} with ID {doc_id}")
            return result
        except Exception as e:
            self.logger.error(f"Error storing document in Elasticsearch: {e}")
            raise

    def scrape_channel(self, channel: Dict[str, Any], config: SlackConfig):
        """Scrape all content from a channel with detailed logging and relationship tracking."""
        channel_id = channel["id"]
        self.logger.info(f"Starting to scrape channel: {channel['name']} ({channel_id})")

        # Get channel permissions and store with relationships
        permissions = self._to_dict(self.slack.get_channel_permissions(channel_id))
        self._store_in_neo4j(permissions, "Channel")
        self._store_in_elasticsearch(permissions, "slack_channels")

        # Get channel messages
        messages = self._to_dict(self.slack.get_channel_messages(channel_id, config=config))
        for message in messages:
            # Store message with channel relationship
            message_data = {
                "id": message["ts"],
                "text": message.get("text", ""),
                "user": message.get("user", ""),
                "channel": channel_id,
                "type": "message",
                "timestamp": message["ts"],
                "reactions": message.get("reactions", []),
                "attachments": message.get("attachments", []),
                "thread_ts": message.get("thread_ts", None),
                "thread_replies": message.get("thread_replies", []),
                "links": message.get("links", []),
            }

            # Store message with channel relationship
            self._store_in_neo4j(
                message_data,
                "Message",
                relationships=[
                    {
                        "source_type": "Message",
                        "source_id": message["ts"],
                        "target_type": "Channel",
                        "target_id": channel_id,
                        "type": "IN_CHANNEL",
                        "properties": {"timestamp": message["ts"]},
                    }
                ],
            )
            self._store_in_elasticsearch(message_data, "slack_messages")

            # Process thread replies if present
            if message.get("thread_replies"):
                for reply in message["thread_replies"]:
                    reply_data = {
                        "id": reply["ts"],
                        "text": reply.get("text", ""),
                        "user": reply.get("user", ""),
                        "channel": channel_id,
                        "type": "message",
                        "timestamp": reply["ts"],
                        "reactions": reply.get("reactions", []),
                        "attachments": reply.get("attachments", []),
                    }
                    self._store_in_neo4j(
                        reply_data,
                        "Message",
                        relationships=[
                            {
                                "source_type": "Message",
                                "source_id": reply["ts"],
                                "target_type": "Message",
                                "target_id": message["ts"],
                                "type": "REPLIES_TO",
                                "properties": {"timestamp": reply["ts"]},
                            },
                            {
                                "source_type": "Message",
                                "source_id": reply["ts"],
                                "target_type": "Channel",
                                "target_id": channel_id,
                                "type": "IN_CHANNEL",
                                "properties": {"timestamp": reply["ts"]},
                            },
                        ],
                    )

            # Process files if present
            if config.include_files and "files" in message:
                for file in message["files"]:
                    file_info = self._to_dict(self.slack.get_file_info(file["id"]))
                    self._store_in_neo4j(
                        file_info,
                        "File",
                        relationships=[
                            {
                                "source_type": "File",
                                "source_id": file["id"],
                                "target_type": "Message",
                                "target_id": message["ts"],
                                "type": "ATTACHED_TO",
                                "properties": {"timestamp": message["ts"]},
                            },
                            {
                                "source_type": "File",
                                "source_id": file["id"],
                                "target_type": "Channel",
                                "target_id": channel_id,
                                "type": "IN_CHANNEL",
                                "properties": {"timestamp": message["ts"]},
                            },
                        ],
                    )
                    self._store_in_elasticsearch(file_info, "slack_files")

            # Process canvases if present
            if config.include_canvases and "blocks" in message:
                for block in message["blocks"]:
                    if block.get("type") == "canvas":
                        canvas_info = self._to_dict(
                            self.slack.get_canvas_content(block["canvas_id"])
                        )
                        self._store_in_neo4j(
                            canvas_info,
                            "Canvas",
                            relationships=[
                                {
                                    "source_type": "Canvas",
                                    "source_id": block["canvas_id"],
                                    "target_type": "Message",
                                    "target_id": message["ts"],
                                    "type": "EMBEDDED_IN",
                                    "properties": {"timestamp": message["ts"]},
                                },
                                {
                                    "source_type": "Canvas",
                                    "source_id": block["canvas_id"],
                                    "target_type": "Channel",
                                    "target_id": channel_id,
                                    "type": "IN_CHANNEL",
                                    "properties": {"timestamp": message["ts"]},
                                },
                            ],
                        )
                        self._store_in_elasticsearch(canvas_info, "slack_canvases")

        # Get channel pins with full content
        pins = self._to_dict(self.slack.get_channel_pins(channel_id))
        for pin in pins:
            pin_data = {
                "id": pin["id"],
                "type": pin["type"],
                "channel": channel_id,
                "timestamp": pin.get("timestamp", None),
                "created_by": pin.get("created_by", None),
                "content": pin.get("content", {}),
            }
            self._store_in_neo4j(
                pin_data,
                "Pin",
                relationships=[
                    {
                        "source_type": "Pin",
                        "source_id": pin["id"],
                        "target_type": "Channel",
                        "target_id": channel_id,
                        "type": "IN_CHANNEL",
                        "properties": {"timestamp": pin.get("timestamp", None)},
                    }
                ],
            )
            self._store_in_elasticsearch(pin_data, "slack_pins")

        # Get channel bookmarks with full content
        bookmarks = self._to_dict(self.slack.get_channel_bookmarks(channel_id))
        for bookmark in bookmarks:
            bookmark_data = {
                "id": bookmark["id"],
                "title": bookmark.get("title", ""),
                "link": bookmark.get("link", ""),
                "channel": channel_id,
                "created_by": bookmark.get("created_by", ""),
                "timestamp": bookmark.get("timestamp", None),
                "type": bookmark.get("type", "link"),
                "emoji": bookmark.get("emoji", None),
                "entity_id": bookmark.get("entity_id", None),
                "content": bookmark.get("content", {}),
            }
            self._store_in_neo4j(
                bookmark_data,
                "Bookmark",
                relationships=[
                    {
                        "source_type": "Bookmark",
                        "source_id": bookmark["id"],
                        "target_type": "Channel",
                        "target_id": channel_id,
                        "type": "IN_CHANNEL",
                        "properties": {"timestamp": bookmark.get("timestamp", None)},
                    }
                ],
            )
            self._store_in_elasticsearch(bookmark_data, "slack_bookmarks")

        # Get channel info and store it
        channel_info_response = self._to_dict(self.slack.get_channel_info(channel_id))
        channel_info = channel_info_response["channel"]
        channel_info["id"] = channel_id
        self._store_in_neo4j(channel_info, "Channel")
        self._store_in_elasticsearch(channel_info, "slack_channels")

        self.logger.info(f"Completed scraping channel: {channel['name']}")


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

    # Create table if it doesn't exist
    metadata.create_all(engine)

    # Store the data
    df.to_sql("slack_users", engine, if_exists="replace", index=False)

    # Add metadata
    context.add_output_metadata(
        {
            "num_users": MetadataValue.int(len(df)),
            "preview": MetadataValue.md(df.head().to_markdown()),
        }
    )

    return df


@asset
def scrape_slack_content(context: AssetExecutionContext, config: SlackConfig) -> Dict[str, Any]:
    """Asset that scrapes all available Slack content and stores it in Neo4j and Elasticsearch."""
    client = SlackClient()
    scraper = SlackScraper(client)

    # Get all public channels
    channels = client.get_public_channels()
    context.log.info(f"Found {len(channels)} public channels")

    # Create indices in Elasticsearch if they don't exist
    indices = [
        "slack_channels",
        "slack_messages",
        "slack_files",
        "slack_canvases",
        "slack_pins",
        "slack_bookmarks",
    ]
    for index in indices:
        if not scraper.es.indices.exists(index=index):
            scraper.es.indices.create(index=index)
            context.log.info(f"Created Elasticsearch index: {index}")

    # Scrape each channel
    for channel in channels:
        context.log.info(f"Scraping channel: {channel['name']}")
        scraper.scrape_channel(channel, config)

    return {"num_channels": len(channels), "status": "completed"}
