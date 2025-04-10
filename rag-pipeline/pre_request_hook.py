#!/usr/bin/env python
# RAG Pre-request Hook for LiteLLM
# This hook is called before each request is sent to the LLM

import json
import logging
from typing import Dict, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def pre_request_hook(
    user_id: Optional[str] = None,
    data: Dict[str, Any] = {},
    model_name: Optional[str] = None,
    call_type: Optional[str] = None,
    api_key: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Pre-request hook for RAG capabilities.
    This function is called before each request is sent to the LLM.
    
    Args:
        user_id: The ID of the user making the request
        data: The request data
        model_name: The name of the model being used
        call_type: The type of call (completion, embedding, etc.)
        api_key: The API key being used
        headers: The headers being sent with the request
        
    Returns:
        Modified request data with RAG context injected
    """
    logger.info(f"Processing request for model: {model_name}, call_type: {call_type}")
    
    try:
        # Only process completion requests
        if call_type != "completion":
            return data
        
        # Extract the prompt/messages from the request
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
        # This is a placeholder for demonstration purposes
        
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
