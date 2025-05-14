import logging
import hashlib
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase
from elasticsearch import Elasticsearch
import os

from .client import SlackClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SlackScraper:
    def __init__(self, slack_client: SlackClient):
        self.client = slack_client
        self.logger = logging.getLogger(__name__)
        self.neo4j = self._init_neo4j()
        self.es = self._init_elasticsearch()

    def _init_neo4j(self):
        return GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
        )

    def _init_elasticsearch(self):
        return Elasticsearch(
            [
                {
                    "scheme": "http",
                    "host": os.getenv("ELASTICSEARCH_HOST", "localhost"),
                    "port": int(os.getenv("ELASTICSEARCH_PORT", "9200")),
                }
            ]
        )

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
        return hashlib.md5(f"{source}:{id}".encode()).hexdigest()

    def _store_in_neo4j(
        self,
        data: Dict[str, Any],
        node_type: str,
        relationships: Optional[List[Dict[str, Any]]] = None,
    ):
        """Store data in Neo4j with relationships."""
        try:
            with self.neo4j.session() as session:
                # Create or update node
                query = f"""
                MERGE (n:{node_type} {{id: $id}})
                SET n += $properties
                RETURN n
                """
                result = session.run(query, id=data["id"], properties=data)
                self.logger.info(f"Stored {node_type} node with ID {data['id']}")

                # Create relationships if specified
                if relationships:
                    for rel in relationships:
                        try:
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
                                properties=rel.get("properties", {})
                            )
                        except Exception as e:
                            self.logger.warning(f"Error creating relationship: {e}")
                return result
        except Exception as e:
            self.logger.error(f"Error storing {node_type} in Neo4j: {e}")
            raise

    def _store_in_elasticsearch(self, data: Dict[str, Any], index: str):
        """Store data in Elasticsearch."""
        try:
            doc_id = self._generate_document_id(data.get("source", "slack"), data["id"])
            result = self.es.index(index=index, id=doc_id, document=data)
            self.logger.info(f"Stored document in {index} with ID {doc_id}")
            return result
        except Exception as e:
            self.logger.error(f"Error storing document in Elasticsearch: {e}")
            raise

    def scrape_channel(self, channel: Dict[str, Any], config: Dict[str, Any]):
        """Scrape a Slack channel and store its data."""
        try:
            channel_id = channel["id"]
            channel_name = channel["name"]
            self.logger.info(f"Scraping channel: {channel_name} ({channel_id})")

            # Get channel info and permissions
            channel_info = self._to_dict(self.client.get_channel_info(channel_id))
            permissions = self._to_dict(self.client.get_channel_permissions(channel_id))

            # Get messages
            messages = self.client.get_channel_messages(
                channel_id,
                max_messages=config.get("max_messages_per_channel", 1000)
            )

            # Get pins and bookmarks if enabled
            pins = []
            bookmarks = []
            if config.get("include_pins", True):
                pins = [self._to_dict(pin) for pin in self.client.get_channel_pins(channel_id)]
            if config.get("include_bookmarks", True):
                bookmarks = [self._to_dict(bookmark) for bookmark in self.client.get_channel_bookmarks(channel_id)]

            # Store channel data
            channel_data = {
                "id": channel_id,
                "name": channel_name,
                "type": "channel",
                "source": "slack",
                "info": channel_info,
                "permissions": permissions,
                "message_count": len(messages),
                "pin_count": len(pins),
                "bookmark_count": len(bookmarks),
                "is_private": channel.get("is_private", False),
                "is_shared": channel.get("is_shared", False),
                "is_org_shared": channel.get("is_org_shared", False),
                "is_global_shared": channel.get("is_global_shared", False),
            }

            # Store in Neo4j
            self._store_in_neo4j(channel_data, "SlackChannel")

            # Store in Elasticsearch
            self._store_in_elasticsearch(channel_data, "slack_channels")

            # Store messages
            for message in messages:
                message_data = {
                    "id": message["ts"],
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "type": "message",
                    "source": "slack",
                    "text": message.get("text", ""),
                    "user": message.get("user"),
                    "timestamp": message["ts"],
                    "thread_ts": message.get("thread_ts"),
                    "reactions": message.get("reactions", []),
                    "attachments": message.get("attachments", []),
                    "files": message.get("files", []),
                }

                # Store in Neo4j
                self._store_in_neo4j(
                    message_data,
                    "SlackMessage",
                    relationships=[{
                        "source_type": "SlackChannel",
                        "target_type": "SlackMessage",
                        "type": "CONTAINS",
                        "source_id": channel_id,
                        "target_id": message["ts"],
                    }]
                )

                # Store in Elasticsearch
                self._store_in_elasticsearch(message_data, "slack_messages")

            # Store pins
            for pin in pins:
                pin_data = {
                    "id": pin["id"],
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "type": "pin",
                    "source": "slack",
                    "message": pin.get("message", {}),
                    "created_by": pin.get("created_by"),
                    "created_at": pin.get("created"),
                }

                # Store in Neo4j
                self._store_in_neo4j(
                    pin_data,
                    "SlackPin",
                    relationships=[{
                        "source_type": "SlackChannel",
                        "target_type": "SlackPin",
                        "type": "HAS_PIN",
                        "source_id": channel_id,
                        "target_id": pin["id"],
                    }]
                )

                # Store in Elasticsearch
                self._store_in_elasticsearch(pin_data, "slack_pins")

            # Store bookmarks
            for bookmark in bookmarks:
                bookmark_data = {
                    "id": bookmark["id"],
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "type": "bookmark",
                    "source": "slack",
                    "title": bookmark.get("title", ""),
                    "link": bookmark.get("link", ""),
                    "emoji": bookmark.get("emoji"),
                    "created_by": bookmark.get("created_by"),
                    "created_at": bookmark.get("created"),
                }

                # Store in Neo4j
                self._store_in_neo4j(
                    bookmark_data,
                    "SlackBookmark",
                    relationships=[{
                        "source_type": "SlackChannel",
                        "target_type": "SlackBookmark",
                        "type": "HAS_BOOKMARK",
                        "source_id": channel_id,
                        "target_id": bookmark["id"],
                    }]
                )

                # Store in Elasticsearch
                self._store_in_elasticsearch(bookmark_data, "slack_bookmarks")

            return {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "message_count": len(messages),
                "pin_count": len(pins),
                "bookmark_count": len(bookmarks),
            }

        except Exception as e:
            self.logger.error(f"Error scraping channel {channel.get('name', 'unknown')}: {e}")
            raise 