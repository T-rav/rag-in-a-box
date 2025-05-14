from elasticsearch import AsyncElasticsearch
from typing import Dict, Any, List, Optional
import os
from loguru import logger
import json

class ElasticsearchService:
    def __init__(self):
        self.es = AsyncElasticsearch(
            [
                {
                    "scheme": "http",
                    "host": os.getenv("ELASTICSEARCH_HOST", "localhost"),
                    "port": int(os.getenv("ELASTICSEARCH_PORT", "9200")),
                }
            ]
        )
        
    async def search_documents(
        self,
        query: str,
        user_email: str = None,  # keep for compatibility but unused
        size: int = 5,
        indices: List[str] = ["google_drive_files", "slack_messages", "web_pages"]  # Restored multiple indices
    ) -> List[Dict[str, Any]]:
        """
        Search for documents across multiple indices using a simple match_all query.
        """
        try:
            # Build a simple match_all query similar to the working curl command
            search_body = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["content"]
                    }
                },
                "size": size
            }
            
            logger.info("Executing Elasticsearch query with body: {}", json.dumps(search_body, indent=2))
            response = await self.es.search(
                index=",".join(indices),
                body=search_body
            )
            
            # Convert response to dict for logging
            response_dict = response.body
            logger.info("Elasticsearch response: {}", json.dumps(response_dict, indent=2))
            
            # Process and format the results
            results = []
            for hit in response_dict["hits"]["hits"]:
                score = hit["_score"]
                source = hit["_source"]
                
                # Extract relevant metadata
                metadata = source.get("meta", {})
                result = {
                    "id": hit["_id"],
                    "content": source.get("content", ""),  # Access content directly from _source
                    "score": score,
                    "metadata": {
                        "source": metadata.get("source", "unknown"),
                        "file_name": metadata.get("file_name"),
                        "created_time": metadata.get("created_time"),
                        "modified_time": metadata.get("modified_time"),
                        "web_link": metadata.get("web_link"),
                        "permissions": metadata.get("permissions", []),
                        "is_public": metadata.get("is_public", False)
                    }
                }
                results.append(result)
                
            logger.info("Found {} relevant documents (no user filter)", len(results))
            return results
            
        except Exception as e:
            logger.error("Error searching documents: {}", str(e), exc_info=True)
            raise
            
    async def close(self):
        """Close the Elasticsearch connection"""
        await self.es.close() 