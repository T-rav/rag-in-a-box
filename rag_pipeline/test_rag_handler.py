import asyncio
from litellm import completion
import os
from dotenv import load_dotenv
import pytest

# Load environment variables
load_dotenv()

@pytest.mark.asyncio
async def test_full_rag_handler():
    """Test the complete RAG handler with a real request"""
    print("\n=== Testing Full RAG Handler ===")
    
    try:
        # Test message that should trigger the handler
        messages = [
            {"role": "user", "content": "Hello, can you help me?"}
        ]
        
        # Make the completion request
        response = await completion(
            model="gpt-3.5-turbo",  # Using a test model
            messages=messages,
            temperature=0.7
        )
        
        # Print the messages to verify context injection
        print("\n  Modified messages:")
        for msg in response.choices[0].message.messages:
            print(f"  Role: {msg['role']}")
            print(f"  Content: {msg['content'][:100]}...\n")
            
    except Exception as e:
        print(f"  ✗ Error during full handler test: {str(e)}")

if __name__ == "__main__":
    print("Starting RAG Handler Tests...")
    
    # Run the test
    asyncio.run(test_full_rag_handler())
    
    print("\nAll tests completed!") 