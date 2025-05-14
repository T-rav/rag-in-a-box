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

async def handle_message(
    text: str,
    user_id: str,
    client: WebClient,
    channel: str,
    thread_ts: Optional[str] = None
):
    print(f"DEBUG: Entered handle_message with text={text}, user_id={user_id}, channel={channel}, thread_ts={thread_ts}")
    try:
        # async with aiohttp.ClientSession() as session:
        #     session.headers.update({"X-Auth-Token": f"slack:{user_id}"})
        #     messages = [
        #         {"role": "system", "content": "You are a helpful assistant. ..."},
        #         {"role": "user", "content": text}
        #     ]
        #     llm_response = await get_llm_response(messages, session=session)
        #     if llm_response:
        #         await client.chat_postMessage(
        #             channel=channel,
        #             text=llm_response,
        #             thread_ts=thread_ts
        #         )
        #     else:
        #         await client.chat_postMessage(
        #             channel=channel,
        #             text="I'm sorry, I encountered an error while generating a response.",
        #             thread_ts=thread_ts
        #         )
        # Instead, just send a static test message:
        print("DEBUG: About to send static test message")
        await client.chat_postMessage(
            channel=channel,
            text="TEST: WORKING MESSAGE RESPONSE",
            thread_ts=thread_ts
        )
        print("DEBUG: Static test message sent successfully")
    except Exception as e:
        print(f"DEBUG: Exception in handle_message: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"Error handling message: {e}")
        await client.chat_postMessage(
            channel=channel,
            text="I'm sorry, something went wrong. Please try again later.",
            thread_ts=thread_ts
        )

@app.event("app_mention")
async def handle_mention(body, say, client):
    """Handle when the bot is mentioned in a channel"""
    print("DEBUG: handle_mention received body (repr):", repr(body))
    print("DEBUG: handle_mention received event (repr):", repr(body["event"]))
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
        print("DEBUG: Exception in handle_mention:", e)
        import traceback
        traceback.print_exc()
        logger.error(f"Error handling mention: {e}")
        await say("I'm sorry, I encountered an error while processing your request.")

@app.event("message")
async def handle_direct_message(body, client):
    """Handle direct messages to the bot"""
    print("DEBUG: handle_direct_message received body (repr):", repr(body))
    print("DEBUG: handle_direct_message received event (repr):", repr(body["event"]))
    try:
        event = body["event"]
        if event.get("bot_id") or event.get("channel_type") != "im":
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
        print("DEBUG: Exception in handle_direct_message:", e)
        import traceback
        traceback.print_exc()
        logger.error(f"Error handling direct message: {e}")
        await client.chat_postMessage(
            channel=event["channel"],
            text="I'm sorry, I encountered an error while processing your request."
        )

def main():
    """Start the Slack bot asynchronously"""
    async def run():
        handler = AsyncSocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
        await handler.start_async()
        print("DEBUG: Slack AsyncApp active sessions (s_… identifiers) reported:", app._session_ids)
    asyncio.run(run())

if __name__ == "__main__":
    main() 