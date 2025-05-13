import os
import logging
from typing import Dict, Any, List, Optional
from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebNeo4jService:
    """Service for handling Neo4j operations for web content."""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password")),
        )
        self.logger = logging.getLogger(__name__)

    def create_or_update_page(self, page_data: Dict[str, Any], relationships: Optional[List[Dict[str, Any]]] = None):
        """Create or update a web page node with relationships."""
        try:
            with self.driver.session() as session:
                # Create or update node
                query = """
                MERGE (n:WebPage {url: $url})
                SET n += $properties
                RETURN n
                """
                properties = {
                    "url": page_data["url"],
                    "title": page_data["title"],
                    "content_type": page_data["content_type"],
                    "timestamp": page_data["timestamp"]
                }
                
                # Add num_pages for PDF files
                if page_data.get("content_type", "").lower().startswith("application/pdf"):
                    properties["num_pages"] = page_data.get("num_pages", 0)
                    properties["author"] = page_data.get("author", "")
                    properties["extraction_method"] = page_data.get("extraction_method", "")
                
                result = session.run(query, url=page_data["url"], properties=properties)
                self.logger.info(f"Stored WebPage node with URL {page_data['url']}")

                # Create relationships if specified
                if relationships:
                    for rel in relationships:
                        try:
                            rel_query = """
                            MATCH (source:WebPage {url: $source_url})
                            MATCH (target:WebPage {url: $target_url})
                            MERGE (source)-[r:LINKS_TO]->(target)
                            SET r += $properties
                            """
                            session.run(
                                rel_query,
                                source_url=rel["source_url"],
                                target_url=rel["target_url"],
                                properties=rel.get("properties", {})
                            )
                        except Exception as e:
                            self.logger.warning(f"Error creating relationship: {e}")
                return result
        except Exception as e:
            self.logger.error(f"Error storing WebPage in Neo4j: {e}")
            raise

    def create_or_update_image(self, image_data: Dict[str, Any], page_url: str):
        """Create or update an image node and link it to its page."""
        try:
            with self.driver.session() as session:
                # Create or update image node
                query = """
                MERGE (i:WebImage {url: $url})
                SET i += $properties
                WITH i
                MATCH (p:WebPage {url: $page_url})
                MERGE (p)-[r:CONTAINS_IMAGE]->(i)
                RETURN i
                """
                properties = {
                    "url": image_data["url"],
                    "alt": image_data.get("alt", ""),
                    "is_valid": image_data.get("is_valid", True)
                }
                
                result = session.run(
                    query,
                    url=image_data["url"],
                    page_url=page_url,
                    properties=properties
                )
                self.logger.info(f"Stored WebImage node with URL {image_data['url']}")
                return result
        except Exception as e:
            self.logger.error(f"Error storing WebImage in Neo4j: {e}")
            raise

    def close(self):
        """Close the Neo4j driver connection."""
        self.driver.close() 