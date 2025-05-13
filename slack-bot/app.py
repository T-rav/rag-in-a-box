import os
import logging
import aiohttp
import asyncio
import json
from typing import Optional, Dict, Any, List
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Slack app
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

# MCP Server configuration
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://mcp:9090")
MCP_API_KEY = os.environ.get("MCP_API_KEY", "")
MCP_TIMEOUT = int(os.environ.get("MCP_TIMEOUT", "30"))

# LLM configuration
LLM_API_URL = os.environ.get("LLM_API_URL", "http://localhost:8000/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4")

async def get_llm_response(
    messages: List[Dict[str, str]],
    session: Optional[aiohttp.ClientSession] = None
) -> Optional[str]:
    """Get response from LLM"""
    if not LLM_API_KEY:
        return None
        
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000
    }
    
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True
        
    try:
        async with session.post(
            f"{LLM_API_URL}/chat/completions",
            headers=headers,
            json=payload,
            timeout=MCP_TIMEOUT
        ) as response:
            if response.status == 200:
                result = await response.json()
                return result["choices"][0]["message"]["content"]
            else:
                error_text = await response.text()
                logger.error(f"LLM API error: {response.status} - {error_text}")
                return None
    except Exception as e:
        logger.error(f"Error calling LLM API: {e}")
        return None
    finally:
        if close_session:
            await session.close()

async def get_context_from_mcp(
    user_id: str,
    prompt: str,
    session: Optional[aiohttp.ClientSession] = None
) -> Optional[Dict[str, Any]]:
    """Get context from MCP server"""
    if not MCP_API_KEY or not user_id or not prompt:
        return None
        
    headers = {
        "Authorization": f"Bearer {MCP_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Send Slack user ID instead of email
    auth_token = f"slack:{user_id}"
    
    payload = {
        "auth_token": auth_token,
        "token_type": "Slack",
        "prompt": prompt,
        "history_summary": None
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

def format_context_for_llm(context: Dict[str, Any]) -> str:
    """Format the MCP context for the LLM prompt"""
    if not context or not context.get("documents"):
        return "No relevant context found."
        
    # Group documents by source
    docs_by_source = {}
    for doc in context["documents"]:
        source = doc["source"]
        if source not in docs_by_source:
            docs_by_source[source] = []
        docs_by_source[source].append(doc["content"])
    
    # Build context string
    context_parts = ["Sources:"]
    for source, docs in docs_by_source.items():
        context_parts.append(f"- {source}: {len(docs)} document(s)")
    
    context_parts.append("\nRelevant content:")
    for doc in context["documents"]:
        context_parts.append(f"\nFrom {doc['source']}:\n{doc['content']}")
    
    return "\n".join(context_parts)

async def handle_message(
    text: str,
    user_id: str,
    client: WebClient,
    channel: str,
    thread_ts: Optional[str] = None
):
    """Handle a message (either DM or mention)"""
    try:
        # Get context from MCP server
        async with aiohttp.ClientSession() as session:
            context = await get_context_from_mcp(
                user_id=user_id,
                prompt=text,
                session=session
            )
            
            # Prepare messages for LLM
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant. Use the following context to inform your response. Begin your response with a 'Sources:' section that lists all the sources you used, followed by your answer. When providing information in your answer, cite your sources using the format 'According to [source]' or 'From [source]'."
                }
            ]
            
            if context and context.get("documents"):
                messages.append({
                    "role": "system",
                    "content": format_context_for_llm(context)
                })
            
            messages.append({
                "role": "user",
                "content": text
            })
            
            # Get response from LLM
            llm_response = await get_llm_response(messages, session)
            
            if llm_response:
                # Send the response
                await client.chat_postMessage(
                    channel=channel,
                    text=llm_response,
                    thread_ts=thread_ts
                )
            else:
                await client.chat_postMessage(
                    channel=channel,
                    text="I'm sorry, I encountered an error while generating a response.",
                    thread_ts=thread_ts
                )
                
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await client.chat_postMessage(
            channel=channel,
            text="I'm sorry, something went wrong. Please try again later.",
            thread_ts=thread_ts
        )

@app.event("app_mention")
async def handle_mention(event, say, client):
    """Handle when the bot is mentioned in a channel"""
    try:
        # Just use the user ID directly from the event
        user_id = event["user"]
        
        # Get the message text, removing the bot mention
        text = event["text"]
        text = text.split(">", 1)[1].strip() if ">" in text else text
        
        # Handle the message
        await handle_message(
            text=text,
            user_id=user_id,
            client=client,
            channel=event["channel"],
            thread_ts=event.get("thread_ts")
        )
        
    except SlackApiError as e:
        logger.error(f"Error handling mention: {e}")
        await say("I'm sorry, I encountered an error while processing your request.")

@app.event("message")
async def handle_direct_message(event, client):
    """Handle direct messages to the bot"""
    try:
        # Ignore messages from bots and non-DM messages
        if event.get("bot_id") or event.get("channel_type") != "im":
            return
            
        # Just use the user ID directly from the event
        user_id = event["user"]
        
        # Handle the message
        await handle_message(
            text=event["text"],
            user_id=user_id,
            client=client,
            channel=event["channel"],
            thread_ts=event.get("thread_ts")
        )
        
    except SlackApiError as e:
        logger.error(f"Error handling direct message: {e}")
        await client.chat_postMessage(
            channel=event["channel"],
            text="I'm sorry, I encountered an error while processing your request."
        )

def main():
    """Start the Slack bot"""
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()

if __name__ == "__main__":
    main() 