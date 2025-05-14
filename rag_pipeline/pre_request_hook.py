import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))
sys.path.insert(0, "/app")

import logging

# Create a custom logger (named "rag_handler") and set its level to INFO.
logger = logging.getLogger("rag_handler")
logger.setLevel(logging.INFO)

# (Optional) Create a file handler (writing to /app/rag_handler.log) and set its level to INFO.
fh = logging.FileHandler("/app/rag_handler.log")
fh.setLevel(logging.INFO)

# (Optional) Create a formatter (for example, "%(asctime)s – %(name)s – %(levelname)s – %(message)s") and assign it to the file handler.
formatter = logging.Formatter("%(asctime)s – %(name)s – %(levelname)s – %(message)s")
fh.setFormatter(formatter)

# (Optional) Add the file handler to our custom logger.
logger.addHandler(fh)

# (Optional) Log (or "print") a message at the very top (outside of any function) so that if the module is imported (even "lazy" or "dynamic") you'll see that log.
logger.info("!!! RAG HANDLER MODULE LOADED (using file logger) !!!")

from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy.proxy_server import UserAPIKeyAuth, DualCache
from typing import Optional, Literal, Dict, Any, List
import json
import aiohttp
import asyncio

# MCP Server configuration
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp:8000")
MCP_API_KEY = os.environ.get("MCP_API_KEY", "")
MCP_TIMEOUT = int(os.environ.get("MCP_TIMEOUT", "30"))  # Timeout in seconds
MCP_MAX_RETRIES = int(os.environ.get("MCP_MAX_RETRIES", "3"))
TOKEN_TYPE = os.environ.get("TOKEN_TYPE", "OpenWebUI")  # Type of JWT token being used

async def get_context_from_mcp(
    api_key: str,
    auth_token: str,
    token_type: str,
    prompt: str,
    history_summary: str,
    session: Optional[aiohttp.ClientSession] = None
) -> Optional[Dict[str, Any]]:
    """Get context from MCP server"""
    if not api_key or not auth_token or not prompt:
        return None
        
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "auth_token": auth_token,
        "token_type": token_type,
        "prompt": prompt,
        "history_summary": history_summary
    }
    
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True
        
    try:
        async with session.post(
            f"{MCP_SERVER_URL}/context",
            headers=headers,
            json=payload,
            timeout=MCP_TIMEOUT
        ) as response:
            if response.status == 200:
                result = await response.json()
                logger.info(f"Successfully retrieved context from MCP server")
                return result
            else:
                error_text = await response.text()
                logger.error(f"MCP server error: {response.status} - {error_text}")
                return None
    except Exception as e:
        logger.error(f"Error calling MCP server: {e}")
        return None
    finally:
        if close_session:
            await session.close()

def summarize_conversation_history(messages: List[Dict[str, str]]) -> str:
    """Create a summary of the conversation history"""
    if not messages:
        return ""
        
    # Only include the last few messages to keep the summary concise
    recent_messages = messages[-5:] if len(messages) > 5 else messages
    
    summary = []
    for msg in recent_messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "").strip()
        if content:
            summary.append(f"{role}: {content[:100]}...")
            
    return "\n".join(summary)

class RAGHandler(CustomLogger):
    def __init__(self):
        self.session = None
        logger.info("RAGHandler initialized")
        
    async def _ensure_session(self):
        """Ensure we have an active aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
            logger.info("Created new aiohttp session")
        return self.session

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,
        call_type: Literal["completion", "text_completion", "embeddings", "image_generation", "moderation", "audio_transcription"]
    ):
        logger.info("=== RAG HANDLER ENTRY POINT ===")
        logger.info(f"Call type: {call_type}")
        logger.info(f"Data keys: {list(data.keys())}")
        
        try:
            # Only process completion requests
            if call_type != "completion":
                logger.info("Skipping non-completion request")
                return data

            # Get the messages from the request
            messages = data.get("messages", [])
            if not messages:
                logger.warning("No messages in request")
                return data

            # Always use default token as expected by MCP server
            auth_token = "default_token"
            logger.info("Using default token for MCP server")
            
            # Get the latest user message
            user_messages = [msg for msg in messages if msg.get("role") == "user"]
            if not user_messages:
                logger.warning("No user messages found")
                return data
                
            latest_user_message = user_messages[-1]["content"]
            logger.info(f"Latest user message: {latest_user_message[:100]}...")
            
            history_summary = summarize_conversation_history(messages[:-1])  # Exclude latest message
            logger.info(f"History summary: {history_summary[:100]}...")
            
            # Get context from MCP server
            session = await self._ensure_session()
            context = await get_context_from_mcp(
                api_key=MCP_API_KEY,
                auth_token=auth_token,
                token_type=TOKEN_TYPE,
                prompt=latest_user_message,
                history_summary=history_summary,
                session=session
            )
            
            # Only modify the request if we got valid context
            if context and context.get("context_items"):
                logger.info(f"Got {len(context['context_items'])} context items from MCP")
                # Build the context string from context items
                context_parts = []
                for item in context["context_items"]:
                    source = item.get("metadata", {}).get("source", "unknown")
                    content = item.get("content", "")
                    if content:
                        # Clean up the content by removing BOM and extra whitespace
                        content = content.replace("\ufeff", "").strip()
                        context_parts.append(f"[{source}]\n{content}\n")
                
                context_str = "\n\n".join(context_parts)
                logger.info(f"Context string length: {len(context_str)}")
                
                # Find or create system message
                system_messages = [msg for msg in messages if msg.get("role") == "system"]
                if system_messages:
                    # Update the system message with context
                    system_messages[0]["content"] = f"{system_messages[0]['content']}\n\nHere are some relevant documents to help answer the user's question:\n\n{context_str}"
                    logger.info("Updated existing system message with context")
                else:
                    # Create new system message with context
                    messages.insert(0, {
                        "role": "system",
                        "content": f"You are a helpful assistant. Here are some relevant documents to help answer the user's question:\n\n{context_str}"
                    })
                    logger.info("Created new system message with context")
                
                # Update the request data
                data["messages"] = messages
                logger.info("Successfully injected context into request")
            else:
                logger.info("No context items received from MCP")
            
        except Exception as e:
            logger.error(f"Error in pre_request_hook: {str(e)}", exc_info=True)
            # On error, return the original data unchanged
            return data
        
        return data

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None
            logger.info("Closed aiohttp session")

# Create an instance of the handler
rag_handler_instance = RAGHandler()
logger.info("Created rag_handler_instance")