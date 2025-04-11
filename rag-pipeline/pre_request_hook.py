from litellm.integrations.custom_logger import CustomLogger
from litellm.proxy.proxy_server import UserAPIKeyAuth, DualCache
from typing import Optional, Literal
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# todo : patch the litellm method that calls this to pass the auth token down to the rag handler
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
            
            # Here you would implement your RAG retrieval logic
            # For example, query a vector database, retrieve relevant documents, etc.
            
            # Placeholder for RAG context
            rag_context = "This is where retrieved context from your knowledge base would be inserted."
            
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

# Create an instance of the handler
rag_handler_instance = RAGHandler()