import hashlib
import logging
from typing import Dict, Any, List
import re
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def compute_hash(content: bytes) -> str:
    """Compute a hash of the content for deduplication."""
    return hashlib.sha256(content).hexdigest()

def extract_links(text: str) -> List[Dict[str, str]]:
    """Extract URLs from text and validate them."""
    # URL regex pattern
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    urls = re.findall(url_pattern, text)
    
    links = []
    for url in urls:
        try:
            parsed = urlparse(url)
            if parsed.scheme and parsed.netloc:  # Basic URL validation
                links.append({
                    "url": url,
                    "domain": parsed.netloc,
                    "is_valid": True
                })
        except Exception as e:
            logger.warning(f"Error parsing URL {url}: {e}")
            links.append({
                "url": url,
                "is_valid": False,
                "error": str(e)
            })
    
    return links

def format_slack_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Slack message for storage, including metadata and content."""
    formatted = {
        "id": message.get("ts", ""),
        "type": "message",
        "source": "slack",
        "text": message.get("text", ""),
        "user": message.get("user"),
        "timestamp": message.get("ts"),
        "thread_ts": message.get("thread_ts"),
        "reactions": message.get("reactions", []),
        "attachments": message.get("attachments", []),
        "files": message.get("files", []),
        "links": extract_links(message.get("text", "")),
    }
    
    # Add metadata
    if "channel" in message:
        formatted["channel_id"] = message["channel"]
    if "team" in message:
        formatted["team_id"] = message["team"]
    
    return formatted

def format_slack_channel(channel: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Slack channel for storage, including metadata."""
    formatted = {
        "id": channel.get("id", ""),
        "type": "channel",
        "source": "slack",
        "name": channel.get("name", ""),
        "is_private": channel.get("is_private", False),
        "is_shared": channel.get("is_shared", False),
        "is_org_shared": channel.get("is_org_shared", False),
        "is_global_shared": channel.get("is_global_shared", False),
        "created": channel.get("created"),
        "creator": channel.get("creator"),
        "num_members": channel.get("num_members", 0),
        "topic": channel.get("topic", {}).get("value", ""),
        "purpose": channel.get("purpose", {}).get("value", ""),
    }
    
    return formatted

def format_slack_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """Format a Slack user for storage, including metadata."""
    profile = user.get("profile", {})
    formatted = {
        "id": user.get("id", ""),
        "type": "user",
        "source": "slack",
        "name": user.get("name", ""),
        "real_name": profile.get("real_name", ""),
        "display_name": profile.get("display_name", ""),
        "email": profile.get("email", ""),
        "team_id": user.get("team_id", ""),
        "is_admin": user.get("is_admin", False),
        "is_owner": user.get("is_owner", False),
        "is_bot": user.get("is_bot", False),
        "is_app_user": user.get("is_app_user", False),
        "deleted": user.get("deleted", False),
    }
    
    return formatted 