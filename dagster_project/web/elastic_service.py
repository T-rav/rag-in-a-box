import os
import logging
import hashlib
from typing import Dict, Any
from elasticsearch import Elasticsearch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebElasticsearchService:
    """Service for handling Elasticsearch operations for web content."""
    
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

    def _generate_document_id(self, url: str) -> str:
        """Generate a unique document ID for Elasticsearch."""
        return hashlib.md5(url.encode()).hexdigest()

    def index_page(self, page_data: Dict[str, Any]):
        """Index a web page in Elasticsearch."""
        try:
            doc_id = self._generate_document_id(page_data["url"])
            
            # Prepare document for indexing
            document = {
                "url": page_data["url"],
                "title": page_data["title"],
                "content": page_data["content"],
                "content_type": page_data["content_type"],
                "timestamp": page_data["timestamp"],
                "depth": page_data.get("depth", 0),
                "links": page_data.get("links", []),
                "images": page_data.get("images", [])
            }
            
            # Add PDF-specific fields
            if page_data.get("content_type", "").lower().startswith("application/pdf"):
                document.update({
                    "author": page_data.get("author", ""),
                    "num_pages": page_data.get("num_pages", 0),
                    "extraction_method": page_data.get("extraction_method", "")
                })
            
            result = self.es.index(index="web_pages", id=doc_id, document=document)
            self.logger.info(f"Indexed web page with URL {page_data['url']}")
            return result
        except Exception as e:
            self.logger.error(f"Error indexing web page in Elasticsearch: {e}")
            raise

    def index_image(self, image_data: Dict[str, Any], page_url: str):
        """Index an image in Elasticsearch."""
        try:
            doc_id = self._generate_document_id(image_data["url"])
            
            document = {
                "url": image_data["url"],
                "alt": image_data.get("alt", ""),
                "is_valid": image_data.get("is_valid", True),
                "page_url": page_url
            }
            
            result = self.es.index(index="web_images", id=doc_id, document=document)
            self.logger.info(f"Indexed image with URL {image_data['url']}")
            return result
        except Exception as e:
            self.logger.error(f"Error indexing image in Elasticsearch: {e}")
            raise

    def search_pages(self, query: str, size: int = 10) -> Dict[str, Any]:
        """Search for web pages in Elasticsearch."""
        try:
            result = self.es.search(
                index="web_pages",
                body={
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": ["title^2", "content", "url"]
                        }
                    },
                    "size": size
                }
            )
            return result
        except Exception as e:
            self.logger.error(f"Error searching web pages in Elasticsearch: {e}")
            raise 