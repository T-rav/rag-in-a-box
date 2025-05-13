from aioredis import Redis, from_url
from typing import Optional, Any, Dict
import json
import os
from datetime import datetime, timedelta
from loguru import logger

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour default

class Cache:
    def __init__(self):
        self.redis: Optional[Redis] = None
        
    async def connect(self):
        """Connect to Redis"""
        if not self.redis:
            self.redis = await from_url(REDIS_URL)
            logger.info(f"Connected to Redis at {REDIS_URL}")
            
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            self.redis = None
            
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis:
            await self.connect()
            
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Error getting value from cache: {e}")
            return None
            
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache with optional TTL"""
        if not self.redis:
            await self.connect()
            
        try:
            await self.redis.set(
                key,
                json.dumps(value),
                ex=ttl or CACHE_TTL
            )
            return True
        except Exception as e:
            logger.error(f"Error setting value in cache: {e}")
            return False
            
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        if not self.redis:
            await self.connect()
            
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error deleting value from cache: {e}")
            return False
            
    # User cache operations
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user from cache"""
        return await self.get(f"user:{user_id}")
        
    async def set_user(
        self,
        user_id: str,
        user_data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Cache user data"""
        return await self.set(f"user:{user_id}", user_data, ttl)
        
    async def delete_user(self, user_id: str) -> bool:
        """Remove user from cache"""
        return await self.delete(f"user:{user_id}")
        
    # Context cache operations
    async def get_context(
        self,
        user_id: str,
        prompt: str
    ) -> Optional[Dict[str, Any]]:
        """Get context from cache"""
        cache_key = f"context:{user_id}:{hash(prompt)}"
        return await self.get(cache_key)
        
    async def set_context(
        self,
        user_id: str,
        prompt: str,
        context: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Cache context"""
        cache_key = f"context:{user_id}:{hash(prompt)}"
        return await self.set(cache_key, context, ttl)
        
    async def delete_context(self, user_id: str, prompt: str) -> bool:
        """Remove context from cache"""
        cache_key = f"context:{user_id}:{hash(prompt)}"
        return await self.delete(cache_key)
        
    # Conversation cache operations
    async def get_conversation(
        self,
        conversation_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get conversation from cache"""
        return await self.get(f"conversation:{conversation_id}")
        
    async def set_conversation(
        self,
        conversation_id: int,
        conversation_data: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """Cache conversation data"""
        return await self.set(f"conversation:{conversation_id}", conversation_data, ttl)
        
    async def delete_conversation(self, conversation_id: int) -> bool:
        """Remove conversation from cache"""
        return await self.delete(f"conversation:{conversation_id}")

# Create global cache instance
cache = Cache() 