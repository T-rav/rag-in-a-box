import logging
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SlackNeo4jService:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
        )
        self.logger = logging.getLogger(__name__)

    def close(self):
        """Close the Neo4j driver connection."""
        self.driver.close()

    def create_or_update_channel(self, channel_data: Dict[str, Any]):
        """Create or update a Slack channel node."""
        try:
            with self.driver.session() as session:
                query = """
                MERGE (c:SlackChannel {id: $id})
                SET c += $properties
                RETURN c
                """
                result = session.run(query, id=channel_data["id"], properties=channel_data)
                self.logger.info(f"Stored SlackChannel node with ID {channel_data['id']}")
                return result
        except Exception as e:
            self.logger.error(f"Error storing SlackChannel in Neo4j: {e}")
            raise

    def create_or_update_message(self, message_data: Dict[str, Any], channel_id: str):
        """Create or update a Slack message node and its relationship to the channel."""
        try:
            with self.driver.session() as session:
                # Create message node
                query = """
                MERGE (m:SlackMessage {id: $id})
                SET m += $properties
                WITH m
                MATCH (c:SlackChannel {id: $channel_id})
                MERGE (c)-[r:CONTAINS]->(m)
                RETURN m
                """
                result = session.run(
                    query,
                    id=message_data["id"],
                    properties=message_data,
                    channel_id=channel_id
                )
                self.logger.info(f"Stored SlackMessage node with ID {message_data['id']}")
                return result
        except Exception as e:
            self.logger.error(f"Error storing SlackMessage in Neo4j: {e}")
            raise

    def create_or_update_user(self, user_data: Dict[str, Any]):
        """Create or update a Slack user node."""
        try:
            with self.driver.session() as session:
                query = """
                MERGE (u:SlackUser {id: $id})
                SET u += $properties
                RETURN u
                """
                result = session.run(query, id=user_data["id"], properties=user_data)
                self.logger.info(f"Stored SlackUser node with ID {user_data['id']}")
                return result
        except Exception as e:
            self.logger.error(f"Error storing SlackUser in Neo4j: {e}")
            raise

    def create_or_update_pin(self, pin_data: Dict[str, Any], channel_id: str):
        """Create or update a Slack pin node and its relationship to the channel."""
        try:
            with self.driver.session() as session:
                query = """
                MERGE (p:SlackPin {id: $id})
                SET p += $properties
                WITH p
                MATCH (c:SlackChannel {id: $channel_id})
                MERGE (c)-[r:HAS_PIN]->(p)
                RETURN p
                """
                result = session.run(
                    query,
                    id=pin_data["id"],
                    properties=pin_data,
                    channel_id=channel_id
                )
                self.logger.info(f"Stored SlackPin node with ID {pin_data['id']}")
                return result
        except Exception as e:
            self.logger.error(f"Error storing SlackPin in Neo4j: {e}")
            raise

    def create_or_update_bookmark(self, bookmark_data: Dict[str, Any], channel_id: str):
        """Create or update a Slack bookmark node and its relationship to the channel."""
        try:
            with self.driver.session() as session:
                query = """
                MERGE (b:SlackBookmark {id: $id})
                SET b += $properties
                WITH b
                MATCH (c:SlackChannel {id: $channel_id})
                MERGE (c)-[r:HAS_BOOKMARK]->(b)
                RETURN b
                """
                result = session.run(
                    query,
                    id=bookmark_data["id"],
                    properties=bookmark_data,
                    channel_id=channel_id
                )
                self.logger.info(f"Stored SlackBookmark node with ID {bookmark_data['id']}")
                return result
        except Exception as e:
            self.logger.error(f"Error storing SlackBookmark in Neo4j: {e}")
            raise

    def create_message_reaction(self, message_id: str, user_id: str, reaction: str):
        """Create a reaction relationship between a user and a message."""
        try:
            with self.driver.session() as session:
                query = """
                MATCH (m:SlackMessage {id: $message_id})
                MATCH (u:SlackUser {id: $user_id})
                MERGE (u)-[r:REACTED_WITH {reaction: $reaction}]->(m)
                RETURN r
                """
                result = session.run(
                    query,
                    message_id=message_id,
                    user_id=user_id,
                    reaction=reaction
                )
                self.logger.info(f"Created reaction relationship for message {message_id}")
                return result
        except Exception as e:
            self.logger.error(f"Error creating reaction relationship: {e}")
            raise

    def create_channel_membership(self, channel_id: str, user_id: str):
        """Create a membership relationship between a user and a channel."""
        try:
            with self.driver.session() as session:
                query = """
                MATCH (c:SlackChannel {id: $channel_id})
                MATCH (u:SlackUser {id: $user_id})
                MERGE (u)-[r:IS_MEMBER_OF]->(c)
                RETURN r
                """
                result = session.run(
                    query,
                    channel_id=channel_id,
                    user_id=user_id
                )
                self.logger.info(f"Created membership relationship for channel {channel_id}")
                return result
        except Exception as e:
            self.logger.error(f"Error creating membership relationship: {e}")
            raise 