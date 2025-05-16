import os
import logging
import aiohttp
import asyncio
from typing import Optional, Dict, Any, List
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Slack app
app = AsyncApp(token=os.environ.get("SLACK_BOT_TOKEN"))

# LLM configuration
LLM_API_URL = os.environ.get("LLM_API_URL", "http://localhost:8000/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4")

# Default suggested prompts - now including agent actions
DEFAULT_PROMPTS = [
    {"text": "Tell me about Insight Mesh", "action_id": "prompt_about"},
    {"text": "How can I query my data?", "action_id": "prompt_query"},
    {"text": "Start a data indexing job", "action_id": "agent_index_data"},
    {"text": "Check job status", "action_id": "agent_check_status"},
    {"text": "Import data from Slack", "action_id": "agent_import_slack"}
    {"text": "Tell me about the actions I can take", "action_id": "prompt_actions"}
]

# Available agent processes
AGENT_PROCESSES = {
    "agent_index_data": {
        "name": "Data Indexing Job",
        "description": "Indexes your documents into the RAG system",
        "command": "python dagster_project/run_job.py index_files"
    },
    "agent_import_slack": {
        "name": "Slack Import Job",
        "description": "Imports data from Slack channels",
        "command": "python dagster_project/slack_assets.py run slack_channels_job"
    },
    # Add more agent processes as needed
}

async def get_llm_response(
    messages: List[Dict[str, str]],
    session: Optional[aiohttp.ClientSession] = None
) -> Optional[str]:
    """Get response from LLM via LiteLLM proxy"""
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
            json=payload
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

async def run_agent_process(process_id: str) -> Dict[str, Any]:
    """Run an agent process in the background and return status info"""
    if process_id not in AGENT_PROCESSES:
        return {"success": False, "message": f"Unknown agent process: {process_id}"}
    
    process = AGENT_PROCESSES[process_id]
    
    try:
        # Create a process to run the command
        process_obj = await asyncio.create_subprocess_shell(
            process["command"],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        # Return immediately with process info
        return {
            "success": True,
            "process_id": process_id,
            "name": process["name"],
            "status": "started",
            "pid": process_obj.pid
        }
    except Exception as e:
        logger.error(f"Error running agent process {process_id}: {e}")
        return {
            "success": False,
            "process_id": process_id,
            "name": process["name"],
            "error": str(e)
        }

async def set_assistant_status(client: WebClient, channel: str, thread_ts: str, status: str = "Thinking..."):
    """Set the assistant status indicator"""
    try:
        await client.assistant_threads_setStatus(
            channel=channel,
            thread_ts=thread_ts,
            status=status
        )
    except SlackApiError as e:
        logger.error(f"Error setting status: {e}")

async def set_suggested_prompts(client: WebClient, channel: str, thread_ts: str, prompts: List[Dict[str, str]] = None):
    """Set suggested prompts for the assistant thread"""
    if prompts is None:
        prompts = DEFAULT_PROMPTS
    
    try:
        await client.assistant_threads_setSuggestedPrompts(
            channel=channel,
            thread_ts=thread_ts,
            suggested_prompts=prompts
        )
    except SlackApiError as e:
        logger.error(f"Error setting suggested prompts: {e}")

async def handle_agent_action(action_id: str, user_id: str, client: WebClient, channel: str, thread_ts: str):
    """Handle agent process actions"""
    logger.info(f"Handling agent action: {action_id}")
    
    if action_id not in AGENT_PROCESSES:
        await client.chat_postMessage(
            channel=channel,
            text=f"Sorry, I couldn't find the requested agent process: {action_id}",
            thread_ts=thread_ts
        )
        return
    
    # Set a status to indicate we're starting the process
    await set_assistant_status(client, channel, thread_ts, f"Starting {AGENT_PROCESSES[action_id]['name']}...")
    
    # Run the agent process
    result = await run_agent_process(action_id)
    
    if result["success"]:
        # Create a rich message with process info
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"🚀 *Agent Process Started*: {result['name']}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:* {result['status']}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Process ID:* {result['pid']}"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Process started by <@{user_id}>"
                    }
                ]
            }
        ]
        
        await client.chat_postMessage(
            channel=channel,
            blocks=blocks,
            text=f"Agent process {result['name']} started successfully.",
            thread_ts=thread_ts
        )
    else:
        await client.chat_postMessage(
            channel=channel,
            text=f"❌ Failed to start agent process: {result.get('error', 'Unknown error')}",
            thread_ts=thread_ts
        )
    
    # Clear the status
    await set_assistant_status(client, channel, thread_ts, "")

async def handle_message(
    text: str,
    user_id: str,
    client: WebClient,
    channel: str,
    thread_ts: Optional[str] = None
):
    logger.info(f"Handling message: {text} from user {user_id} in channel {channel}, thread {thread_ts}")
    
    # Check if this is an agent action trigger
    for prompt in DEFAULT_PROMPTS:
        if prompt["action_id"].startswith("agent_") and text.lower() == prompt["text"].lower():
            await handle_agent_action(prompt["action_id"], user_id, client, channel, thread_ts)
            return
    
    try:
        # Set thinking status if in a thread
        if thread_ts:
            await set_assistant_status(client, channel, thread_ts, "Thinking...")
        
        # Use the LLM to generate a response
        async with aiohttp.ClientSession() as session:
            session.headers.update({"X-Auth-Token": f"slack:{user_id}"})
            messages = [
                {"role": "system", "content": "You are a helpful assistant for Insight Mesh, a RAG (Retrieval-Augmented Generation) system. You help users understand and work with their data. You can also start agent processes on behalf of users when they request it."},
                {"role": "user", "content": text}
            ]
            
            llm_response = await get_llm_response(messages, session=session)
            
            # Send the response and clear status
            if llm_response:
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
            
            # Clear the status if we were in a thread
            if thread_ts:
                await set_assistant_status(client, channel, thread_ts, "")
                
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        if thread_ts:
            await set_assistant_status(client, channel, thread_ts, "")
        
        await client.chat_postMessage(
            channel=channel,
            text="I'm sorry, something went wrong. Please try again later.",
            thread_ts=thread_ts
        )

@app.event("assistant_thread_started")
async def handle_assistant_thread_started(body, client):
    """Handle the event when a user starts an AI assistant thread"""
    logger.info("Assistant thread started")
    try:
        event = body["event"]
        channel_id = event["context"]["channel_id"]
        thread_ts = event.get("thread_ts")
        user_id = event.get("user")
        
        # Set suggested prompts
        await set_suggested_prompts(client, channel_id, thread_ts)
        
        # Optional: send a welcome message
        await client.chat_postMessage(
            channel=channel_id,
            text="👋 Hello! I'm Insight Mesh Assistant. I can help answer questions about your data or start agent processes for you. Try one of the suggested actions above!",
            thread_ts=thread_ts
        )
    except Exception as e:
        logger.error(f"Error handling assistant thread started: {e}")

@app.event("assistant_thread_context_changed")
async def handle_context_changed(body, client):
    """Handle when the context (channel) changes"""
    logger.info("Assistant thread context changed")
    try:
        event = body["event"]
        channel_id = event["context"]["channel_id"]
        thread_ts = event.get("thread_ts")
        
        # Optional: update the assistant's context
        # For now, we'll just acknowledge the context change
        logger.info(f"Context changed to channel: {channel_id}")
    except Exception as e:
        logger.error(f"Error handling context change: {e}")

@app.event("message.im")
async def handle_im_message(body, client):
    """Handle messages in DMs (AI Apps use this for messages)"""
    logger.info("Received DM message for AI app")
    try:
        event = body["event"]
        if event.get("bot_id"):  # Skip messages from bots
            return
            
        user_id = event["user"]
        channel = event["channel"]
        text = event["text"]
        thread_ts = event.get("thread_ts")
        
        await handle_message(
            text=text,
            user_id=user_id,
            client=client,
            channel=channel,
            thread_ts=thread_ts
        )
    except Exception as e:
        logger.error(f"Error handling IM message: {e}")
        await client.chat_postMessage(
            channel=event["channel"],
            text="I'm sorry, I encountered an error while processing your request.",
            thread_ts=event.get("thread_ts")
        )

# Keep legacy event handlers for backward compatibility
@app.event("app_mention")
async def handle_mention(body, say, client):
    """Handle when the bot is mentioned in a channel"""
    logger.info("Received app mention")
    try:
        user_id = body["event"]["user"]
        text = body["event"]["text"]
        text = text.split("<@", 1)[-1].split(">", 1)[-1].strip() if ">" in text else text
        
        await handle_message(
            text=text,
            user_id=user_id,
            client=client,
            channel=body["event"]["channel"],
            thread_ts=body["event"].get("thread_ts")
        )
    except Exception as e:
        logger.error(f"Error handling mention: {e}")
        await say("I'm sorry, I encountered an error while processing your request.")

@app.event("message")
async def handle_direct_message(body, client):
    """Handle regular direct messages to the bot (legacy support)"""
    logger.info("Received direct message event")
    try:
        event = body["event"]
        # Skip if it's from a bot or not a DM
        if event.get("bot_id") or event.get("channel_type") != "im":
            return
            
        # Skip if it's already handled by message.im (prevent duplicates)
        if event.get("subtype") == "message.im":
            return
            
        user_id = event["user"]
        await handle_message(
            text=event["text"],
            user_id=user_id,
            client=client,
            channel=event["channel"],
            thread_ts=event.get("thread_ts")
        )
    except Exception as e:
        logger.error(f"Error handling direct message: {e}")
        await client.chat_postMessage(
            channel=event["channel"],
            text="I'm sorry, I encountered an error while processing your request."
        )

def main():
    """Start the Slack bot asynchronously"""
    async def run():
        handler = AsyncSocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
        logger.info("Starting Insight Mesh Assistant with AI Apps support...")
        await handler.start_async()
    asyncio.run(run())

if __name__ == "__main__":
    main() 