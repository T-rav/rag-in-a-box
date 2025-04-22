from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy.proxy_server import UserAPIKeyAuth, DualCache
from typing import Optional, Literal
import logging
import requests
import json
import os

# TODO: Implement OpenWebUI integration to fetch user email based on the ID in the JWT token
# TODO: Cache email lookups in Redis to avoid repeated API calls to OpenWebUI

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure the Haystack search endpoint from environment variables
HAYSTACK_ENDPOINT = os.environ.get("HAYSTACK_ENDPOINT", "http://haystack:8000/search")
MAX_RESULTS = int(os.environ.get("HAYSTACK_MAX_RESULTS", "3"))

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
            
            # Get authorization header if available
            auth_header = headers.get("authorization", "")
            
            # Call Haystack search endpoint
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