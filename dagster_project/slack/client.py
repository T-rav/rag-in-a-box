import os
import logging
import json
import time
from typing import Optional, Dict, Any, List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        """Convert a Slack response object to a dictionary."""
        if hasattr(obj, "data"):
            return obj.data
        elif isinstance(obj, dict):
            return {k: self._to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._to_dict(item) for item in obj]
        return obj

    def _flatten_dict(
        self, d: Dict[str, Any], parent_key: str = "", sep: str = "_"
    ) -> Dict[str, Any]:
        """Flatten a nested dictionary by concatenating keys with a separator."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            elif isinstance(v, list):
                # Convert list to string representation
                items.append((new_key, json.dumps(v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def _handle_rate_limit(self, e: SlackApiError) -> None:
        """Handle rate limiting by waiting and retrying."""
        if e.response["error"] == "ratelimited":
            retry_after = int(e.response.headers.get("Retry-After", self.rate_limit_delay))
            self.logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            return True
        return False

    def _make_slack_call(self, call_func, *args, **kwargs):
        """Make a Slack API call with rate limit handling."""
        max_retries = 3
        current_retry = 0

        while current_retry < max_retries:
            try:
                response = call_func(*args, **kwargs)
                time.sleep(self.rate_limit_delay)  # Add delay between calls
                return response
            except SlackApiError as e:
                if self._handle_rate_limit(e):
                    current_retry += 1
                    continue
                raise

        raise SlackApiError("Max retries exceeded for rate limiting", None)

    def send_message(
        self, channel: str, text: str, blocks: Optional[list] = None
    ) -> Dict[str, Any]:
        """Send a message to a Slack channel."""
        return self._make_slack_call(
            self.client.chat_postMessage, channel=channel, text=text, blocks=blocks
        )

    def get_channel_info(self, channel: str) -> Dict[str, Any]:
        """Get information about a Slack channel."""
        return self._make_slack_call(self.client.conversations_info, channel=channel)

    def get_users(self) -> List[Dict[str, Any]]:
        """Get all users from the Slack workspace."""
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
        """Get user emails from the Slack workspace."""
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
        """Get all public channels in the workspace."""
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

    def get_channel_messages(
        self, channel_id: str, oldest: Optional[str] = None, max_messages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get messages from a channel with reactions and metadata."""
        try:
            # Join the channel if not already a member
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
                if max_messages and messages_processed >= max_messages:
                    self.logger.info(
                        f"Reached max messages limit ({max_messages}) for channel {channel_id}"
                    )
                    break

                self.logger.info(
                    f"Fetching messages batch for channel {channel_id} (cursor: {cursor})"
                )
                response = self._make_slack_call(
                    self.client.conversations_history,
                    channel=channel_id,
                    cursor=cursor,
                    limit=min(100, max_messages - messages_processed) if max_messages else 100,
                    oldest=oldest,
                )
                messages.extend(response["messages"])
                messages_processed += len(response["messages"])

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            return messages
        except SlackApiError as e:
            self.logger.error(f"Error getting messages for channel {channel_id}: {e}")
            raise

    def get_channel_pins(self, channel_id: str) -> List[Dict[str, Any]]:
        """Get pins from a channel."""
        try:
            pins = []
            cursor = None

            while True:
                response = self._make_slack_call(
                    self.client.pins_list, channel=channel_id, cursor=cursor
                )
                pins.extend(response["items"])

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            return pins
        except SlackApiError as e:
            self.logger.error(f"Error getting pins for channel {channel_id}: {e}")
            raise

    def get_channel_bookmarks(self, channel_id: str) -> List[Dict[str, Any]]:
        """Get bookmarks from a channel."""
        try:
            bookmarks = []
            cursor = None

            while True:
                response = self._make_slack_call(
                    self.client.bookmarks_list, channel_id=channel_id, cursor=cursor
                )
                bookmarks.extend(response["bookmarks"])

                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            return bookmarks
        except SlackApiError as e:
            self.logger.error(f"Error getting bookmarks for channel {channel_id}: {e}")
            raise

    def get_canvas_content(self, canvas_id: str) -> Dict[str, Any]:
        """Get content from a Slack canvas."""
        try:
            return self._make_slack_call(self.client.canvas_get, canvas_id=canvas_id)
        except SlackApiError as e:
            self.logger.error(f"Error getting canvas content for {canvas_id}: {e}")
            raise

    def get_file_info(self, file_id: str) -> Dict[str, Any]:
        """Get information about a file."""
        try:
            return self._make_slack_call(self.client.files_info, file=file_id)
        except SlackApiError as e:
            self.logger.error(f"Error getting file info for {file_id}: {e}")
            raise

    def get_channel_permissions(self, channel_id: str) -> Dict[str, Any]:
        """Get channel permissions and access information."""
        try:
            # Get channel info
            channel_info = self.get_channel_info(channel_id)
            
            # Get channel members
            members = []
            cursor = None
            while True:
                response = self._make_slack_call(
                    self.client.conversations_members,
                    channel=channel_id,
                    cursor=cursor,
                    limit=1000
                )
                members.extend(response["members"])
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

            # Get user info for each member
            member_details = []
            for member_id in members:
                try:
                    user_info = self._make_slack_call(self.client.users_info, user=member_id)
                    member_details.append(user_info["user"])
                except SlackApiError as e:
                    self.logger.warning(f"Could not get user info for {member_id}: {e}")

            return {
                "channel_info": channel_info,
                "members": member_details,
                "is_private": channel_info["channel"].get("is_private", False),
                "is_shared": channel_info["channel"].get("is_shared", False),
                "is_org_shared": channel_info["channel"].get("is_org_shared", False),
                "is_global_shared": channel_info["channel"].get("is_global_shared", False),
            }
        except SlackApiError as e:
            self.logger.error(f"Error getting channel permissions for {channel_id}: {e}")
            raise 