from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy.proxy_server import UserAPIKeyAuth, DualCache
from typing import Optional, Literal, Dict, Any, List
import logging
import json
import os
import aiohttp
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        "Authorization": f"Bearer {api_key}",
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
        
    async def _ensure_session(self):
        """Ensure we have an active aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,
        call_type: Literal["completion", "text_completion", "embeddings", "image_generation", "moderation", "audio_transcription"]
    ):
        try:
            # Only process completion requests
            if call_type != "completion":
                return data

            # Get the messages from the request
            messages = data.get("messages", [])
            if not messages:
                return data

            # Get authorization header if available
            headers = data.get("proxy_server_request", {}).get("headers", {})
            auth_header = headers.get("authorization", "")
            if not auth_header:
                logger.warning("No authorization header found, skipping context retrieval")
                return data

            # Extract token part
            auth_token = auth_header[7:] if auth_header.startswith("Bearer ") else auth_header
            
            # Get the latest user message
            user_messages = [msg for msg in messages if msg.get("role") == "user"]
            if not user_messages:
                return data
                
            latest_user_message = user_messages[-1]["content"]
            history_summary = summarize_conversation_history(messages[:-1])  # Exclude latest message
            
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
            if context and context.get("documents"):
                # Build the context string from documents
                context_parts = []
                for doc in context["documents"]:
                    source = doc.get("source", "unknown")
                    content = doc.get("content", "")
                    if content:
                        context_parts.append(f"[{source}] {content}")
                
                context_str = "\n".join(context_parts)
                
                # Find or create system message
                system_messages = [msg for msg in messages if msg.get("role") == "system"]
                if system_messages:
                    # Just append the documents as reference
                    system_messages[0]["content"] = f"{system_messages[0]['content']}\n\nReference documents:\n{context_str}"
                else:
                    # Create minimal system message with just the documents
                    messages.insert(0, {
                        "role": "system",
                        "content": f"You are a helpful assistant. Reference documents:\n{context_str}"
                    })
                
                # Update the request data
                data["messages"] = messages
                logger.info("Successfully injected context documents")
            
        except Exception as e:
            logger.error(f"Error in pre_request_hook: {str(e)}")
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

# Create an instance of the handler
rag_handler_instance = RAGHandler()