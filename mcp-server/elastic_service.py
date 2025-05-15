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
        user_email: str = None,  # Will be used for permission filtering
        size: int = 5,
        indices: List[str] = ["google_drive_files", "slack_messages", "web_pages"]
    ) -> List[Dict[str, Any]]:
        """
        Search for documents across multiple indices with permission filtering based on user_email.
        """
        try:
            # Build the search query with permission filtering if user_email is provided
            if user_email:
                logger.info(f"Searching documents with permission filtering for email: {user_email}")
                # Build a query that includes email-based permission filtering
                search_body = {
                    "query": {
                        "bool": {
                            "must": {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["content"]
                                }
                            },
                            "should": [
                                # Match public documents
                                {"term": {"meta.is_public": True}},
                                # Match documents where user's email is in accessible_by_emails
                                {"term": {"meta.accessible_by_emails.keyword": user_email}},
                                # Match domain-based access if the user's email contains a domain
                                # e.g., if user_email is "user@example.com", match documents accessible by "example.com"
                                {"term": {"meta.accessible_by_domains.keyword": user_email.split("@")[1] if "@" in user_email else ""}},
                            ],
                            "minimum_should_match": 1
                        }
                    },
                    "size": size
                }
            else:
                # Without user_email, fall back to the simple query with no permission filtering
                logger.info("No user email provided, searching without permission filtering")
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
                
            logger.info("Found {} relevant documents after permission filtering", len(results))
            return results
            
        except Exception as e:
            logger.error("Error searching documents: {}", str(e), exc_info=True)
            raise
            
    async def close(self):
        """Close the Elasticsearch connection"""
        await self.es.close() 