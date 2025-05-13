from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from loguru import logger
import time
from database import (
    get_user_by_id,
    get_user_by_email,
    create_user,
    get_openwebui_user_by_email,
    get_user_contexts,
    create_context,
    get_conversation_history,
    create_conversation,
    add_message
)
from cache import cache
from elastic_service import ElasticsearchService

class ContextService:
    def __init__(self):
        self.cache = cache
        self.es = ElasticsearchService()
        
    async def get_or_create_user(
        self,
        user_id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        openwebui_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get or create a user, using cache when possible"""
        # Try cache first
        cached_user = await self.cache.get_user(user_id)
        if cached_user:
            return cached_user
            
        # Try database
        user = await get_user_by_id(user_id)
        if user:
            # Cache the user
            user_data = {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at.isoformat(),
                "updated_at": user.updated_at.isoformat() if user.updated_at else None,
                "is_active": user.is_active,
                "metadata": user.metadata,
                "openwebui_id": user.openwebui_id
            }
            await self.cache.set_user(user_id, user_data)
            return user_data
            
        # If we have an email but no OpenWebUI ID, try to find the OpenWebUI user
        if email and not openwebui_id:
            openwebui_user = await get_openwebui_user_by_email(email)
            if openwebui_user:
                openwebui_id = openwebui_user.id
                if not name:
                    name = openwebui_user.name
            
        # Create new user if we have enough information
        if email:
            user = await create_user(
                user_id=user_id,
                email=email,
                name=name,
                openwebui_id=openwebui_id
            )
            user_data = {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "created_at": user.created_at.isoformat(),
                "updated_at": None,
                "is_active": True,
                "metadata": {},
                "openwebui_id": user.openwebui_id
            }
            await self.cache.set_user(user_id, user_data)
            return user_data
            
        return None
        
    async def get_context_for_prompt(
        self,
        user_id: str,
        prompt: str,
        history_summary: Optional[str] = None,
        user_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Get relevant documents for a user's prompt"""
        start_time = time.time()
        
        # Try cache first
        cached_context = await self.cache.get_context(user_id, prompt)
        if cached_context:
            cached_context["cache_hit"] = True
            cached_context["retrieval_time_ms"] = int((time.time() - start_time) * 1000)
            return cached_context
            
        # Get user's email for permission filtering
        user_email = user_info.get("email") if user_info else None
        if not user_email:
            logger.warning("No user email provided for context retrieval")
            return {"documents": [], "retrieval_time_ms": int((time.time() - start_time) * 1000)}
            
        try:
            # Search for relevant documents
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
            
            # Cache the context
            await self.cache.set_context(user_id, prompt, context)
            
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
        """Update conversation with a new message"""
        # Get or create conversation
        conversations = await get_conversation_history(user_id, limit=1)
        if conversations:
            conversation = conversations[0]
        else:
            conversation = await create_conversation(
                user_id=user_id,
                title=content[:50] + "..." if len(content) > 50 else content
            )
            
        # Add message
        message = await add_message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            metadata=metadata
        )
        
        # Update cache
        conversation_data = {
            "id": conversation.id,
            "user_id": user_id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": [
                {
                    "role": message.role,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                    "metadata": message.metadata
                }
            ]
        }
        await self.cache.set_conversation(conversation.id, conversation_data)
        
        return conversation_data

    async def close(self):
        """Clean up resources"""
        await self.es.close()

# Create global context service instance
context_service = ContextService() 