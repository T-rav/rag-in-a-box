import os
import hashlib
import logging
from typing import Dict, Any, List, Optional
from .client import SlackClient
from .neo4j_service import Neo4jService
from .elastic_service import ElasticsearchService

class SlackScraper:
    def __init__(self, slack_client: SlackClient, neo4j_service: Neo4jService, elastic_service: ElasticsearchService):
        self.slack = slack_client
        self.neo4j = neo4j_service
        self.es = elastic_service
        self.logger = logging.getLogger(__name__)

    def _to_dict(self, obj):
        if hasattr(obj, "data"):
            return obj.data
        elif isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._to_dict(item) for item in obj]
        return obj

    def _generate_document_id(self, source: str, id: str) -> str:
        return hashlib.md5(f"{source}_{id}".encode()).hexdigest()

    # ... (rest of SlackScraper methods as in slack_assets.py, updated to use self.neo4j and self.es) ... 