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
            # Log headers from the request data
            headers = data.get("proxy_server_request", {}).get("headers", {})
            logger.info("=== RAG PRE-REQUEST HOOK CALLED ===")
            
            # Get authorization header if available
            auth_header = headers.get("authorization", "")
            if not auth_header:
                logger.warning("No authorization header found")
                return data
                
            # Extract token part
            auth_token = auth_header[7:] if auth_header.startswith("Bearer ") else auth_header
            
            # Only process completion requests
            if call_type != "completion":
                return data
            
            # Extract the messages from the request
            messages = data.get("messages", [])
            if not messages:
                return data
            
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
            
            # Add context to system message if available
            if context and context.get("documents"):
                # Group documents by source
                docs_by_source = {}
                for doc in context["documents"]:
                    source = doc["source"]
                    if source not in docs_by_source:
                        docs_by_source[source] = []
                    docs_by_source[source].append(doc["content"])
                
                # Build the context string with sources at the top
                context_parts = []
                
                # Add source summary at the top
                source_summary = "Sources used:\n"
                for source, docs in docs_by_source.items():
                    source_summary += f"- {source}: {len(docs)} document(s)\n"
                context_parts.append(source_summary)
                
                # Add document contents
                context_parts.append("\nRelevant content:")
                for doc in context["documents"]:
                    context_parts.append(f"\nFrom {doc['source']}:\n{doc['content']}")
                
                context_str = "\n".join(context_parts)
                
                # Update or create system message
                system_messages = [msg for msg in messages if msg.get("role") == "system"]
                if system_messages:
                    system_messages[0]["content"] = f"{system_messages[0]['content']}\n\nBegin your response with a 'Sources:' section that lists all the sources you used, followed by your answer. When providing information in your answer, cite your sources using the format 'According to [source]' or 'From [source]'. For example:\n\nSources:\n- google_drive (2 documents)\n- slack (1 document)\n- web (2 documents)\n\nAccording to google_drive: [information]\nFrom slack: [information]\n\nUse the following context to inform your response:\n\n{context_str}"
                else:
                    messages.insert(0, {
                        "role": "system",
                        "content": f"You are a helpful assistant. Begin your response with a 'Sources:' section that lists all the sources you used, followed by your answer. When providing information in your answer, cite your sources using the format 'According to [source]' or 'From [source]'. For example:\n\nSources:\n- google_drive (2 documents)\n- slack (1 document)\n- web (2 documents)\n\nAccording to google_drive: [information]\nFrom slack: [information]\n\nUse the following context to inform your response:\n\n{context_str}"
                    })
                
                # Update the request data with the modified messages
                data["messages"] = messages
                logger.info("Successfully injected context into request")
            
        except Exception as e:
            logger.error(f"Error in pre_request_hook: {str(e)}")
        
        return data

    async def __aenter__(self):
        """Ensure session is created when used as async context manager"""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up session when done"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

# Create an instance of the handler
rag_handler_instance = RAGHandler()