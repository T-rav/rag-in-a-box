from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
import time
# from database import (
#     get_user_by_id,
#     get_user_by_email,
#     create_user,
#     get_openwebui_user_by_email,
#     get_user_contexts,
#     create_context,
#     get_conversation_history,
#     create_conversation,
#     add_message
# )
# from cache import cache
from elastic_service import ElasticsearchService

class ContextService:
    def __init__(self):
        # self.cache = cache
        self.es = ElasticsearchService()
        
    async def get_or_create_user(
        self,
        user_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        openwebui_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get or create a user, using cache when possible"""
        # Commented out all DB/cache logic, just return dummy user
        return {
            "id": user_id,
            "email": email or "dummy@example.com",
            "name": name or "Dummy User",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": None,
            "is_active": True,
            "metadata": {},
            "openwebui_id": openwebui_id
        }
        
    async def get_context_for_prompt(
        self,
        user_id: str,
        prompt: str,
        history_summary: Optional[str] = None,
        user_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get relevant documents for a user's prompt"""
        start_time = time.time()
        
        # Try cache first (disabled)
        # cached_context = await self.cache.get_context(user_id, prompt)
        # if cached_context:
        #     cached_context["cache_hit"] = True
        #     cached_context["retrieval_time_ms"] = int((time.time() - start_time) * 1000)
        #     return cached_context
        
        # Use user_email for permission filtering
        user_email = user_info.get("email") if user_info else None
        if not user_email:
            logger.warning("No user email provided for context retrieval")
            return {"documents": [], "retrieval_time_ms": int((time.time() - start_time) * 1000)}
        
        try:
            # Search for relevant documents with user filter
            documents = await self.es.search_documents(
                query=prompt,
                user_email=user_email,
                size=5  # Limit to top 5 most relevant documents
            )
            
            # Return just the documents with their sources
            context = {
                "documents": [
                    {
                        "content": doc["content"],
                        "source": doc["metadata"].get("source", "unknown").split("_")[0]  # google_drive_files -> google_drive
                    }
                    for doc in documents
                ],
                "retrieval_time_ms": int((time.time() - start_time) * 1000)
            }
            
            # Cache the context (disabled)
            # await self.cache.set_context(user_id, prompt, context)
            
            return context
            
        except Exception as e:
            logger.error("Error retrieving documents: {}", str(e), exc_info=True)
            return {"documents": [], "retrieval_time_ms": int((time.time() - start_time) * 1000)}
        
    async def update_conversation(
        self,
        user_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update conversation with a new message (DB disabled)"""
        # Commented out DB logic, just return dummy conversation
        return {
            "id": "dummy_conversation",
            "user_id": user_id,
            "title": content[:50] + "..." if len(content) > 50 else content,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "messages": [
                {
                    "role": role,
                    "content": content,
                    "created_at": datetime.utcnow().isoformat(),
                    "metadata": metadata or {}
                }
            ]
        }

    async def close(self):
        """Clean up resources"""
        await self.es.close()

# Create global context service instance
context_service = ContextService() 