import os
import time
import json
import logging
import re
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackClient:
    def __init__(self, token: Optional[str] = None, rate_limit_delay: float = 1.0):
        self.token = token or os.getenv("SLACK_BOT_TOKEN")
        if not self.token:
            raise ValueError(
                "Slack bot token not found. Please set SLACK_BOT_TOKEN environment variable or pass token directly."
            )
        self.client = WebClient(token=self.token)
        self.logger = logging.getLogger(__name__)
        self.rate_limit_delay = rate_limit_delay

    def _to_dict(self, obj):
        if hasattr(obj, "data"):
            return obj.data
        elif isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._to_dict(item) for item in obj]
        return obj

    def _flatten_dict(self, d: Dict[str, Any], parent_key: str = "", sep: str = "_") -> Dict[str, Any]:
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                items.append((new_key, json.dumps(v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def _handle_rate_limit(self, e: SlackApiError) -> None:
        if e.response["error"] == "ratelimited":
            retry_after = int(e.response.headers.get("Retry-After", self.rate_limit_delay))
            self.logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            return True
        return False

    def _make_slack_call(self, call_func, *args, **kwargs):
        max_retries = 3
        current_retry = 0
        while current_retry < max_retries:
            try:
                response = call_func(*args, **kwargs)
                time.sleep(self.rate_limit_delay)
                return response
            except SlackApiError as e:
                if self._handle_rate_limit(e):
                    current_retry += 1
                    continue
                raise
        raise SlackApiError("Max retries exceeded for rate limiting", None)

    def send_message(self, channel: str, text: str, blocks: Optional[list] = None) -> Dict[str, Any]:
        return self._make_slack_call(
            self.client.chat_postMessage, channel=channel, text=text, blocks=blocks
        )

    def get_channel_info(self, channel: str) -> Dict[str, Any]:
        return self._make_slack_call(self.client.conversations_info, channel=channel)

    def get_users(self) -> List[Dict[str, Any]]:
        users = []
        cursor = None
        while True:
            response = self._make_slack_call(self.client.users_list, cursor=cursor)
            users.extend(response["members"])
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        return users

    def get_user_emails(self) -> List[Dict[str, str]]:
        users = self.get_users()
        user_emails = []
        for user in users:
            if not user.get("deleted") and user.get("profile", {}).get("email"):
                user_emails.append(
                    {
                        "slack_id": user["id"],
                        "slack_username": user["name"],
                        "email": user["profile"]["email"],
                        "real_name": user["profile"].get("real_name", ""),
                        "display_name": user["profile"].get("display_name", ""),
                    }
                )
        return user_emails

    def get_public_channels(self) -> List[Dict[str, Any]]:
        channels = []
        cursor = None
        while True:
            self.logger.info(f"Fetching channels batch (cursor: {cursor})")
            response = self._make_slack_call(
                self.client.conversations_list, types="public_channel", cursor=cursor, limit=1000
            )
            channels.extend(response["channels"])
            self.logger.info(f"Found {len(response['channels'])} channels in this batch")
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        self.logger.info(f"Total public channels found: {len(channels)}")
        return channels

    def get_channel_messages(self, channel_id: str, oldest: Optional[str] = None, config: Optional[Any] = None) -> List[Dict[str, Any]]:
        try:
            try:
                self._make_slack_call(self.client.conversations_join, channel=channel_id)
                self.logger.info(f"Joined channel {channel_id}")
            except SlackApiError as e:
                if e.response["error"] != "already_in_channel":
                    raise
            messages = []
            cursor = None
            messages_processed = 0
            while True:
                if config and messages_processed >= config.max_messages_per_channel:
                    self.logger.info(
                        f"Reached max messages limit ({config.max_messages_per_channel}) for channel {channel_id}"
                    )
                    break
                self.logger.info(
                    f"Fetching messages batch for channel {channel_id} (cursor: {cursor})"
                )
                response = self._make_slack_call(
                    self.client.conversations_history,
                    channel=channel_id,
                    cursor=cursor,
                    limit=(
                        min(100, config.max_messages_per_channel - messages_processed)
                        if config
                        else 100
                    ),
                    oldest=oldest,
                    include_all_metadata=True,
                )
                batch_messages = response["messages"]
                self.logger.info(f"Found {len(batch_messages)} messages in this batch")
                for message in batch_messages:
                    if config and config.include_reactions:
                        try:
                            reactions = self._make_slack_call(
                                self.client.reactions_get,
                                channel=channel_id,
                                timestamp=message["ts"],
                            )
                            message["reactions"] = reactions.get("message", {}).get("reactions", [])
                        except SlackApiError as e:
                            self.logger.warning(
                                f"Could not get reactions for message {message['ts']}: {e}"
                            )
                            message["reactions"] = []
                    if config and config.include_threads and message.get("thread_ts"):
                        try:
                            thread = self._make_slack_call(
                                self.client.conversations_replies,
                                channel=channel_id,
                                ts=message["thread_ts"],
                            )
                            message["thread_replies"] = thread.get("messages", [])
                        except SlackApiError as e:
                            self.logger.warning(
                                f"Could not get thread replies for message {message['ts']}: {e}"
                            )
                            message["thread_replies"] = []
                    if config and config.include_links:
                        message["links"] = self._extract_links(message.get("text", ""))
                messages.extend(batch_messages)
                messages_processed += len(batch_messages)
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break
            self.logger.info(f"Total messages processed for channel {channel_id}: {len(messages)}")
            return messages
        except SlackApiError as e:
            self.logger.error(f"Error getting messages: {e.response['error']}")
            raise

    def _extract_links(self, text: str) -> List[Dict[str, str]]:
        links = []
        url_pattern = r'https?://[^\s<>"']+|www\.[^\s<>"']+'
        for url in re.findall(url_pattern, text):
            try:
                parsed = urlparse(url)
                if parsed.scheme or parsed.netloc:
                    links.append(
                        {"url": url, "domain": parsed.netloc, "path": parsed.path, "is_valid": True}
                    )
            except Exception as e:
                self.logger.warning(f"Error parsing URL {url}: {e}")
        return links

    # ... (other methods as needed) ... 