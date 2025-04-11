import asyncio
from litellm import completion
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_rag_handler():
    try:
        # Test message that should trigger RAG
        messages = [
            {"role": "user", "content": "What is the capital of France?"}
        ]
        
        # Make the completion request
        response = await completion(
            model="gpt-4o",  # Using the model from our config
            messages=messages,
            temperature=0.7,
        )
        
        # Print the response to see if our RAG context was injected
        print("\nResponse:")
        print(response.choices[0].message.content)
        
        # Print the messages to verify RAG context injection
        print("\nModified messages:")
        for msg in response.choices[0].message.messages:
            print(f"Role: {msg['role']}")
            print(f"Content: {msg['content']}\n")
            
    except Exception as e:
        print(f"Error during test: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_rag_handler()) 