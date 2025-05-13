from elasticsearch import AsyncElasticsearch
from typing import Dict, Any, List, Optional
import os
from loguru import logger

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
        user_email: str,
        size: int = 5,
        indices: List[str] = ["google_drive_files", "slack_messages", "web_pages"]
    ) -> List[Dict[str, Any]]:
        """
        Search for documents across multiple indices with user permission filtering.
        
        Args:
            query: The search query
            user_email: The user's email for permission filtering
            size: Maximum number of results to return
            indices: List of indices to search in
            
        Returns:
            List of documents with their content and metadata
        """
        try:
            # Build the search query with permission filtering
            search_body = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["content^3", "meta.file_name^2", "meta.topic^2"],
                                    "type": "best_fields",
                                    "tie_breaker": 0.3
                                }
                            }
                        ],
                        "filter": [
                            {
                                "bool": {
                                    "should": [
                                        # Public documents
                                        {"term": {"meta.is_public": True}},
                                        # Documents accessible by user's email
                                        {"term": {"meta.accessible_by_emails": user_email}},
                                        # Documents accessible by user's domain
                                        {"prefix": {"meta.accessible_by_domains": user_email.split("@")[1]}}
                                    ],
                                    "minimum_should_match": 1
                                }
                            }
                        ]
                    }
                },
                "size": size,
                "_source": {
                    "includes": [
                        "content",
                        "meta.*"
                    ]
                }
            }
            
            logger.debug("Executing Elasticsearch query: {}", search_body)
            response = await self.es.search(
                index=",".join(indices),
                body=search_body
            )
            
            # Process and format the results
            results = []
            for hit in response["hits"]["hits"]:
                score = hit["_score"]
                source = hit["_source"]
                
                # Extract relevant metadata
                metadata = source.get("meta", {})
                result = {
                    "id": hit["_id"],
                    "content": source.get("content", ""),
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
                
            logger.info("Found {} relevant documents for user {}", len(results), user_email)
            return results
            
        except Exception as e:
            logger.error("Error searching documents: {}", str(e), exc_info=True)
            raise
            
    async def close(self):
        """Close the Elasticsearch connection"""
        await self.es.close() 