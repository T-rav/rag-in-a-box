from typing import Optional, Dict, Any
from datetime import datetime
from loguru import logger
import time
from elastic_service import ElasticsearchService
from models import DocumentResult, ContextResult, UserInfo

class ContextService:
    def __init__(self):
        self.es = ElasticsearchService()
        
    async def get_context_for_prompt(
        self,
        user_id: str,
        prompt: str,
        history_summary: Optional[str] = None,
        user_info: Optional[UserInfo] = None
    ) -> ContextResult:
        """Get relevant documents for a user's prompt"""
        start_time = time.time()
        
        # Use user_email for permission filtering
        user_email = user_info.email if user_info else None
        if not user_email:
            logger.warning("No user email provided for context retrieval")
            return ContextResult(
                documents=[],
                retrieval_time_ms=int((time.time() - start_time) * 1000)
            )
        
        try:
            # Search for relevant documents with user filter
            documents = await self.es.search_documents(
                query=prompt,
                user_email=user_email,
                size=5  # Limit to top 5 most relevant documents
            )
            
            # Create document results using Pydantic models
            document_results = [
                DocumentResult(
                    content=doc["content"],
                    source=doc["metadata"].get("source", "unknown").split("_")[0]  # google_drive_files -> google_drive
                )
                for doc in documents
            ]
            
            # Return context using Pydantic model
            return ContextResult(
                documents=document_results,
                retrieval_time_ms=int((time.time() - start_time) * 1000)
            )
            
        except Exception as e:
            logger.error("Error retrieving documents: {}", str(e), exc_info=True)
            return ContextResult(
                documents=[],
                retrieval_time_ms=int((time.time() - start_time) * 1000)
            )

    async def close(self):
        """Clean up resources"""
        await self.es.close()

# Create global context service instance
context_service = ContextService() 