import asyncio
from litellm import completion
import os
from dotenv import load_dotenv
import jwt
import time
from pre_request_hook import extract_user_info_from_token, get_user_email_from_db

# Load environment variables
load_dotenv()

def generate_test_jwt():
    """Generate a test JWT token with user information"""
    payload = {
        "sub": "test-user-123",
        "email": "test@example.com",
        "exp": int(time.time()) + 3600  # Expires in 1 hour
    }
    
    # For testing, we can use a simple secret
    # In production, this would be a secure secret key
    secret = "test-secret-key"
    
    token = jwt.encode(payload, secret, algorithm="HS256")
    return f"Bearer {token}"

async def test_rag_handler():
    try:
        # Create a test JWT token
        auth_header = generate_test_jwt()
        print(f"\nTest JWT Token: {auth_header}")
        
        # Test user info extraction
        user_info = extract_user_info_from_token(auth_header)
        print("\nExtracted User Info:")
        print(f"  User ID: {user_info['user_id']}")
        print(f"  Email: {user_info['email']}")
        print(f"  Domain: {user_info['domain']}")
        
        # Test message that should trigger RAG
        messages = [
            {"role": "user", "content": "What is the capital of France?"}
        ]
        
        # Make the completion request with auth header
        response = await completion(
            model="gpt-4o",  # Using the model from our config
            messages=messages,
            temperature=0.7,
            request_headers={"authorization": auth_header}  # Pass the auth header
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

async def test_db_lookup():
    """Test database lookup functionality"""
    try:
        # This assumes you have a database connection
        # If not, this test will return None, which is expected
        print("\nTesting Database Lookup:")
        
        # Test with an existing user ID
        user_id = "test-user-123"
        email = get_user_email_from_db(user_id)
        print(f"  Lookup for user '{user_id}': {email or 'Not found'}")
        
        # Test with non-existing user ID
        user_id = "non-existent-user"
        email = get_user_email_from_db(user_id)
        print(f"  Lookup for user '{user_id}': {email or 'Not found'}")
        
    except Exception as e:
        print(f"Error during database test: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_rag_handler())
    # Uncomment to test database lookup separately
    # asyncio.run(test_db_lookup()) 