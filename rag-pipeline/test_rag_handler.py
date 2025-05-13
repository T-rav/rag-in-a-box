import asyncio
from litellm import completion
import os
from dotenv import load_dotenv
import jwt
import time
from pre_request_hook import extract_user_info_from_token, get_user_email_from_db, get_db_connection

# Load environment variables
load_dotenv()

def generate_test_jwt(user_id="test-user-123", email="test@example.com"):
    """Generate a test JWT token with user information"""
    payload = {
        "sub": user_id,
        "email": email,
        "exp": int(time.time()) + 3600  # Expires in 1 hour
    }
    
    # For testing, we can use a simple secret
    # In production, this would be a secure secret key
    secret = "test-secret-key"
    
    token = jwt.encode(payload, secret, algorithm="HS256")
    return f"Bearer {token}"

async def test_token_extraction():
    """Test JWT token extraction and user info parsing"""
    print("\n=== Testing Token Extraction ===")
    
    # Test cases for token extraction
    test_cases = [
        {
            "name": "Valid token with email",
            "token": generate_test_jwt("user-123", "test@example.com"),
            "expected_email": "test@example.com",
            "expected_id": "user-123"
        },
        {
            "name": "Valid token without email",
            "token": generate_test_jwt("user-456", None),
            "expected_email": None,
            "expected_id": "user-456"
        },
        {
            "name": "Invalid token",
            "token": "Bearer invalid.token.here",
            "expected_email": None,
            "expected_id": None
        },
        {
            "name": "Empty token",
            "token": "",
            "expected_email": None,
            "expected_id": None
        }
    ]
    
    for case in test_cases:
        print(f"\nTesting: {case['name']}")
        user_info = extract_user_info_from_token(case['token'])
        print(f"  Token: {case['token'][:30]}...")
        print(f"  Extracted User ID: {user_info['user_id']}")
        print(f"  Extracted Email: {user_info['email']}")
        print(f"  Extracted Domain: {user_info['domain']}")
        
        # Verify results
        if user_info['user_id'] == case['expected_id'] and user_info['email'] == case['expected_email']:
            print("  ✓ Test passed")
        else:
            print("  ✗ Test failed")
            print(f"  Expected ID: {case['expected_id']}, Email: {case['expected_email']}")

async def test_database_lookup():
    """Test database lookup functionality"""
    print("\n=== Testing Database Lookup ===")
    
    # First verify database connection
    conn = get_db_connection()
    if not conn:
        print("  ✗ Database connection failed - skipping database tests")
        return
    
    conn.close()
    print("  ✓ Database connection successful")
    
    # Test cases for database lookup
    test_cases = [
        {
            "name": "Existing user with email",
            "user_id": "test-user-123",
            "expected_result": "test@example.com"  # Update this to match your test data
        },
        {
            "name": "Non-existing user",
            "user_id": "non-existent-user-999",
            "expected_result": None
        },
        {
            "name": "Empty user ID",
            "user_id": "",
            "expected_result": None
        }
    ]
    
    for case in test_cases:
        print(f"\nTesting: {case['name']}")
        email = get_user_email_from_db(case['user_id'])
        print(f"  User ID: {case['user_id']}")
        print(f"  Retrieved Email: {email}")
        
        # Verify results
        if email == case['expected_result']:
            print("  ✓ Test passed")
        else:
            print("  ✗ Test failed")
            print(f"  Expected: {case['expected_result']}")

async def test_full_rag_handler():
    """Test the complete RAG handler with a real request"""
    print("\n=== Testing Full RAG Handler ===")
    
    try:
        # Create a test JWT token
        auth_header = generate_test_jwt()
        print(f"  Test JWT Token: {auth_header[:30]}...")
        
        # Test message that should trigger the handler
        messages = [
            {"role": "user", "content": "Hello, can you help me?"}
        ]
        
        # Make the completion request with auth header
        response = await completion(
            model="gpt-3.5-turbo",  # Using a test model
            messages=messages,
            temperature=0.7,
            request_headers={"authorization": auth_header}
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
    
    # Run all tests
    asyncio.run(test_token_extraction())
    asyncio.run(test_database_lookup())
    asyncio.run(test_full_rag_handler())
    
    print("\nAll tests completed!") 