import logging
import hashlib
from typing import Dict, Any, Optional
from elasticsearch import Elasticsearch
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SlackElasticsearchService:
    def __init__(self):
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
        self._ensure_indices()

    def _ensure_indices(self):
        """Ensure that all required indices exist with proper mappings."""
        indices = {
            "slack_channels": {
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "name": {"type": "keyword"},
                        "type": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "is_private": {"type": "boolean"},
                        "is_shared": {"type": "boolean"},
                        "is_org_shared": {"type": "boolean"},
                        "is_global_shared": {"type": "boolean"},
                        "created": {"type": "date"},
                        "creator": {"type": "keyword"},
                        "num_members": {"type": "integer"},
                        "topic": {"type": "text"},
                        "purpose": {"type": "text"},
                        "message_count": {"type": "integer"},
                        "pin_count": {"type": "integer"},
                        "bookmark_count": {"type": "integer"},
                    }
                }
            },
            "slack_messages": {
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "channel_id": {"type": "keyword"},
                        "channel_name": {"type": "keyword"},
                        "type": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "text": {"type": "text"},
                        "user": {"type": "keyword"},
                        "timestamp": {"type": "date"},
                        "thread_ts": {"type": "keyword"},
                        "reactions": {"type": "nested"},
                        "attachments": {"type": "nested"},
                        "files": {"type": "nested"},
                        "links": {"type": "nested"},
                    }
                }
            },
            "slack_users": {
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "name": {"type": "keyword"},
                        "real_name": {"type": "text"},
                        "display_name": {"type": "text"},
                        "email": {"type": "keyword"},
                        "type": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "team_id": {"type": "keyword"},
                        "is_admin": {"type": "boolean"},
                        "is_owner": {"type": "boolean"},
                        "is_bot": {"type": "boolean"},
                        "is_app_user": {"type": "boolean"},
                        "deleted": {"type": "boolean"},
                    }
                }
            },
            "slack_pins": {
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "channel_id": {"type": "keyword"},
                        "channel_name": {"type": "keyword"},
                        "type": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "message": {"type": "object"},
                        "created_by": {"type": "keyword"},
                        "created_at": {"type": "date"},
                    }
                }
            },
            "slack_bookmarks": {
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "channel_id": {"type": "keyword"},
                        "channel_name": {"type": "keyword"},
                        "type": {"type": "keyword"},
                        "source": {"type": "keyword"},
                        "title": {"type": "text"},
                        "link": {"type": "keyword"},
                        "emoji": {"type": "keyword"},
                        "created_by": {"type": "keyword"},
                        "created_at": {"type": "date"},
                    }
                }
            }
        }

        for index, mapping in indices.items():
            if not self.es.indices.exists(index=index):
                self.es.indices.create(index=index, body=mapping)
                self.logger.info(f"Created index: {index}")

    def _generate_document_id(self, source: str, id: str) -> str:
        """Generate a unique document ID for Elasticsearch."""
        return hashlib.md5(f"{source}:{id}".encode()).hexdigest()

    def index_channel(self, channel_data: Dict[str, Any]):
        """Index a Slack channel document."""
        try:
            doc_id = self._generate_document_id("slack", channel_data["id"])
            result = self.es.index(index="slack_channels", id=doc_id, document=channel_data)
            self.logger.info(f"Indexed channel document with ID {doc_id}")
            return result
        except Exception as e:
            self.logger.error(f"Error indexing channel document: {e}")
            raise

    def index_message(self, message_data: Dict[str, Any]):
        """Index a Slack message document."""
        try:
            doc_id = self._generate_document_id("slack", message_data["id"])
            result = self.es.index(index="slack_messages", id=doc_id, document=message_data)
            self.logger.info(f"Indexed message document with ID {doc_id}")
            return result
        except Exception as e:
            self.logger.error(f"Error indexing message document: {e}")
            raise

    def index_user(self, user_data: Dict[str, Any]):
        """Index a Slack user document."""
        try:
            doc_id = self._generate_document_id("slack", user_data["id"])
            result = self.es.index(index="slack_users", id=doc_id, document=user_data)
            self.logger.info(f"Indexed user document with ID {doc_id}")
            return result
        except Exception as e:
            self.logger.error(f"Error indexing user document: {e}")
            raise

    def index_pin(self, pin_data: Dict[str, Any]):
        """Index a Slack pin document."""
        try:
            doc_id = self._generate_document_id("slack", pin_data["id"])
            result = self.es.index(index="slack_pins", id=doc_id, document=pin_data)
            self.logger.info(f"Indexed pin document with ID {doc_id}")
            return result
        except Exception as e:
            self.logger.error(f"Error indexing pin document: {e}")
            raise

    def index_bookmark(self, bookmark_data: Dict[str, Any]):
        """Index a Slack bookmark document."""
        try:
            doc_id = self._generate_document_id("slack", bookmark_data["id"])
            result = self.es.index(index="slack_bookmarks", id=doc_id, document=bookmark_data)
            self.logger.info(f"Indexed bookmark document with ID {doc_id}")
            return result
        except Exception as e:
            self.logger.error(f"Error indexing bookmark document: {e}")
            raise

    def search_messages(self, query: str, size: int = 10, **kwargs):
        """Search for messages using Elasticsearch query."""
        try:
            body = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["text^3", "channel_name^2", "user"],
                        "type": "best_fields",
                        "tie_breaker": 0.3
                    }
                },
                "size": size,
                "sort": [{"timestamp": "desc"}]
            }
            result = self.es.search(index="slack_messages", body=body, **kwargs)
            return result
        except Exception as e:
            self.logger.error(f"Error searching messages: {e}")
            raise

    def search_channels(self, query: str, size: int = 10, **kwargs):
        """Search for channels using Elasticsearch query."""
        try:
            body = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["name^3", "topic^2", "purpose"],
                        "type": "best_fields",
                        "tie_breaker": 0.3
                    }
                },
                "size": size
            }
            result = self.es.search(index="slack_channels", body=body, **kwargs)
            return result
        except Exception as e:
            self.logger.error(f"Error searching channels: {e}")
            raise 