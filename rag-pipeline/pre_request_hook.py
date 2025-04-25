from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy.proxy_server import UserAPIKeyAuth, DualCache
from typing import Optional, Literal
import logging
import requests
import json
import os
import redis
import jwt
import psycopg2
from psycopg2.extras import DictCursor
import base64

# TODO: Implement OpenWebUI integration to fetch user email based on the ID in the JWT token
# TODO: Cache email lookups in Redis to avoid repeated API calls to OpenWebUI

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure the Haystack search endpoint from environment variables
HAYSTACK_ENDPOINT = os.environ.get("HAYSTACK_ENDPOINT", "http://haystack:8000/search")
MAX_RESULTS = int(os.environ.get("HAYSTACK_MAX_RESULTS", "3"))

# Redis configuration for caching
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
REDIS_TTL = int(os.environ.get("REDIS_TTL", "3600"))  # Cache TTL in seconds (1 hour default)
REDIS_ENABLED = os.environ.get("REDIS_ENABLED", "true").lower() == "true"

# Database configuration for user lookup
DB_HOST = os.environ.get("DB_HOST", "postgres")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "openwebui")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")
DB_TABLE = os.environ.get("DB_USER_TABLE", "users")  # The table containing user data

# Initialize Redis client if enabled
redis_client = None
if REDIS_ENABLED:
    try:
        redis_client = redis.from_url(REDIS_URL)
        logger.info(f"Connected to Redis at {REDIS_URL}")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")

def get_db_connection():
    """
    Create a connection to the PostgreSQL database
    """
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        logger.info(f"Connected to PostgreSQL database at {DB_HOST}:{DB_PORT}/{DB_NAME}")
        return connection
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def get_cached_email(user_id: str) -> Optional[str]:
    """
    Get email from Redis cache by user ID
    """
    if not redis_client:
        return None
        
    try:
        cache_key = f"user_email:{user_id}"
        cached_email = redis_client.get(cache_key)
        if cached_email:
            email = cached_email.decode('utf-8')
            logger.info(f"Cache hit: Found email {email} for user ID {user_id}")
            return email
        return None
    except Exception as e:
        logger.error(f"Error accessing Redis cache: {e}")
        return None

def cache_email(user_id: str, email: str) -> bool:
    """
    Store email in Redis cache with TTL
    """
    if not redis_client or not email:
        return False
        
    try:
        cache_key = f"user_email:{user_id}"
        redis_client.setex(cache_key, REDIS_TTL, email)
        logger.info(f"Cached email {email} for user ID {user_id} for {REDIS_TTL} seconds")
        return True
    except Exception as e:
        logger.error(f"Error writing to Redis cache: {e}")
        return False

def get_user_email_from_db(user_id: str) -> Optional[str]:
    """
    Get user email from database by user ID
    """
    if not user_id:
        return None
        
    try:
        # First check cache
        cached_email = get_cached_email(user_id)
        if cached_email:
            return cached_email
            
        # Connect to the database
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to connect to database for user lookup")
            return None
            
        try:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                # Query to get user email by ID
                query = f"SELECT email FROM {DB_TABLE} WHERE id = %s"
                cursor.execute(query, (user_id,))
                result = cursor.fetchone()
                
                if result and result['email']:
                    email = result['email']
                    logger.info(f"Found email {email} for user ID {user_id} in database")
                    
                    # Cache the result
                    cache_email(user_id, email)
                    return email
                else:
                    logger.warning(f"User ID {user_id} not found in database or has no email")
                    return None
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error looking up user email in database: {e}")
        return None

def extract_user_info_from_token(auth_header: str) -> dict:
    """
    Extract user information from the authorization header
    
    Args:
        auth_header: The HTTP Authorization header value
        
    Returns:
        Dict with user_id, email, domain information
    """
    user_info = {
        "user_id": None,
        "email": None,
        "domain": None
    }
    
    if not auth_header:
        return user_info
    
    try:
        # Extract token part
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = auth_header
            
        try:
            # Use verify=False for tokens you can't verify
            decoded = jwt.decode(token, options={"verify_signature": False})
            
            # Extract user info from decoded token
            user_info["user_id"] = decoded.get("sub") or decoded.get("id")
            user_info["email"] = decoded.get("email")
                
        except jwt.PyJWTError as e:
            # If JWT decoding fails, try manual base64 decoding as fallback
            logger.warning(f"JWT decode error: {e}, trying manual decode")
            
            # JWT tokens have three parts separated by dots
            parts = token.split('.')
            if len(parts) >= 2:
                # The payload is the second part
                padded = parts[1] + '=' * (4 - len(parts[1]) % 4)
                try:
                    payload = json.loads(base64.b64decode(padded).decode('utf-8'))
                    user_info["user_id"] = payload.get("sub") or payload.get("id")
                    user_info["email"] = payload.get("email")
                except Exception as decode_err:
                    logger.error(f"Error in manual token decoding: {decode_err}")
                    
        # If we have a user ID but no email, look it up in the database
        if user_info["user_id"] and not user_info["email"]:
            logger.info(f"Looking up email for user ID: {user_info['user_id']}")
            user_info["email"] = get_user_email_from_db(user_info["user_id"])
            
        # Extract domain from email
        if user_info["email"] and "@" in user_info["email"]:
            user_info["domain"] = user_info["email"].split("@")[1]
                    
    except Exception as e:
        logger.error(f"Error extracting user info from token: {e}")
    
    return user_info

class RAGHandler(CustomLogger):
    def __init__(self):
        pass

    async def async_pre_call_hook(
        self,
        user_api_key_dict: UserAPIKeyAuth,
        cache: DualCache,
        data: dict,
        call_type: Literal["completion", "text_completion", "embeddings", "image_generation", "moderation", "audio_transcription"]
    ):
        try:
            # Log all headers from the request data
            headers = data.get("proxy_server_request", {}).get("headers", {})
            logger.info("=== RAG PRE-REQUEST HOOK CALLED ===")
            logger.info(f"Headers received: {headers}")
            
            # Get authorization header if available
            auth_header = headers.get("authorization", "")
            
            # Extract user information from the token
            user_info = extract_user_info_from_token(auth_header)
            logger.info(f"User info extracted: {user_info}")
            
            # Only process completion requests
            if call_type != "completion":
                return data
            
            # Extract the messages from the request
            messages = data.get("messages", [])
            if not messages or len(messages) == 0:
                return data
            
            # Get the latest user message
            user_messages = [msg for msg in messages if msg.get("role") == "user"]
            if not user_messages:
                return data
                
            latest_user_message = user_messages[-1]
            query = latest_user_message.get("content", "")
            
            # Call Haystack search endpoint with user authorization
            search_headers = {}
            if auth_header:
                search_headers["Authorization"] = auth_header
                
            rag_context = self.get_search_results(query, auth_header)
            
            # Create a system message with the RAG context if it doesn't exist
            system_messages = [msg for msg in messages if msg.get("role") == "system"]
            
            if system_messages:
                # Update existing system message with RAG context
                system_messages[0]["content"] = f"{system_messages[0]['content']}\n\nRelevant context: {rag_context}"
            else:
                # Insert a new system message at the beginning with RAG context
                messages.insert(0, {
                    "role": "system",
                    "content": f"You are a helpful assistant. Please use the following context to inform your response: {rag_context}"
                })
            
            # Update the request data with the modified messages
            data["messages"] = messages
            
            logger.info("Successfully injected RAG context into request")
            
        except Exception as e:
            logger.error(f"Error in pre_request_hook: {str(e)}")
            # Return original data on error to avoid breaking the request
        
        return data
    
    def get_search_results(self, query, auth_header=None):
        """
        Call the Haystack search endpoint to retrieve relevant documents.
        
        Args:
            query: The user's query
            auth_header: The authorization header to pass to the search endpoint
            
        Returns:
            A string containing the retrieved context
        """
        try:
            # Set up headers
            headers = {"Content-Type": "application/json"}
            if auth_header:
                headers["Authorization"] = auth_header
                
            # Prepare the search request
            search_data = {
                "query": query,
                "top_k": MAX_RESULTS
            }
            
            logger.info(f"Calling Haystack search with query: {query}")
            
            # Make the request to the search endpoint
            response = requests.post(
                HAYSTACK_ENDPOINT,
                headers=headers,
                data=json.dumps(search_data),
                timeout=10
            )
            
            # Check if the request was successful
            if response.status_code == 200:
                search_results = response.json()
                documents = search_results.get("documents", [])
                
                if not documents:
                    logger.info("No documents found in search results")
                    return "No relevant documents found for the query."
                
                # Format the retrieved documents
                context_parts = []
                for i, doc in enumerate(documents, 1):
                    content = doc.get("content", "").strip()
                    if content:
                        source = doc.get("meta", {}).get("source", "Unknown source")
                        filename = doc.get("meta", {}).get("filename", "Unknown file")
                        context_parts.append(f"Document {i} (Source: {filename}):\n{content}\n")
                
                # Join all document parts into a single context string
                rag_context = "\n".join(context_parts)
                
                logger.info(f"Retrieved {len(documents)} documents from search")
                return rag_context
            else:
                logger.error(f"Search request failed with status code {response.status_code}: {response.text}")
                return "Error retrieving relevant documents."
                
        except Exception as e:
            logger.error(f"Error in get_search_results: {str(e)}")
            return "Error retrieving relevant documents."

# Create an instance of the handler
rag_handler_instance = RAGHandler()