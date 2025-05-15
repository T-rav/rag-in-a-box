import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
from datetime import datetime
import jwt
from fastapi.testclient import TestClient
from httpx import AsyncClient
import os

# Patch environment variables for testing
os.environ["MCP_API_KEY"] = "test_api_key"
os.environ["JWT_SECRET_KEY"] = "test_secret_key"

# Import after environment variables are set
from main import app
from models import (
    ContextRequest, 
    ContextResponse, 
    ContextItem, 
    ContextSource, 
    ResponseMetadata, 
    RetrievalMetadata,
    UserInfo,
    ContextResult,
    DocumentResult
)

@pytest.fixture
def client():
    """Create a test client."""
    with TestClient(app) as client:
        yield client

@pytest.fixture
def test_context_result():
    """Create a sample context result for testing."""
    return ContextResult(
        documents=[
            DocumentResult(
                content="Q1 goals include increasing revenue by 15%",
                source="google_drive"
            ),
            DocumentResult(
                content="Team objectives for the quarter",
                source="slack"
            )
        ],
        retrieval_time_ms=150,
        cache_hit=False
    )

class TestMainAPI:
    """Tests for the main API endpoints."""
    
    def test_health_check(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
    
    @pytest.mark.asyncio
    async def test_get_context_with_openwebui_token(self, test_context_result):
        """Test getting context with an OpenWebUI token."""
        # Create a mock context service that returns our test result
        with patch("main.context_service") as mock_context_service:
            # Set up the get_context_for_prompt method
            async def mock_get_context(*args, **kwargs):
                return test_context_result
                
            mock_context_service.get_context_for_prompt.side_effect = mock_get_context
            
            # Create a test client that works with async endpoints
            async with AsyncClient(app=app, base_url="http://test") as ac:
                # Create a sample OpenWebUI token
                token_payload = {
                    "sub": "user123",
                    "email": "tmfrisinger@gmail.com",
                    "name": "Test User",
                    "exp": datetime.now().timestamp() + 3600  # 1 hour expiration
                }
                token = jwt.encode(token_payload, "not_verified", algorithm="HS256")
                
                # Create a context request
                request = ContextRequest(
                    auth_token=token,
                    token_type="OpenWebUI",
                    prompt="What are our Q1 goals?",
                    history_summary="Previous conversation about company plans."
                )
                
                # Make the request
                response = await ac.post(
                    "/context",
                    json=request.dict(),
                    headers={"X-API-Key": "test_api_key"}
                )
                
                # Check response
                assert response.status_code == 200
                response_data = response.json()
                
                # Validate that the response follows the MCP protocol
                assert "context_items" in response_data
                assert len(response_data["context_items"]) == 2
                
                # Check the first context item
                context_item = response_data["context_items"][0]
                assert context_item["role"] == "system"
                assert "Q1 goals include increasing revenue by 15%" in context_item["content"]
                assert context_item["metadata"]["source"] == "google_drive"
                
                # Check metadata
                assert "metadata" in response_data
                metadata = response_data["metadata"]
                assert metadata["token_type"] == "OpenWebUI"
                assert "user" in metadata
                assert metadata["user"]["id"] == "user123"
                assert metadata["user"]["email"] == "tmfrisinger@gmail.com"
    
    @pytest.mark.asyncio
    async def test_get_context_with_slack_token(self, test_context_result):
        """Test getting context with a Slack token."""
        # Create a mock context service that returns our test result
        with patch("main.context_service") as mock_context_service:
            # Set up the get_context_for_prompt method
            async def mock_get_context(*args, **kwargs):
                return test_context_result
                
            mock_context_service.get_context_for_prompt.side_effect = mock_get_context
            
            # Create a test client that works with async endpoints
            async with AsyncClient(app=app, base_url="http://test") as ac:
                # Create a sample Slack token
                token = "slack:U123456"
                
                # Create a context request
                request = ContextRequest(
                    auth_token=token,
                    token_type="Slack",
                    prompt="What are our Q1 goals?",
                    history_summary="Previous conversation about company plans."
                )
                
                # Make the request
                response = await ac.post(
                    "/context",
                    json=request.dict(),
                    headers={"X-API-Key": "test_api_key"}
                )
                
                # Check response
                assert response.status_code == 200
                response_data = response.json()
                
                # Validate that the response follows the MCP protocol
                assert "context_items" in response_data
                assert len(response_data["context_items"]) == 2
                
                # Check metadata
                assert "metadata" in response_data
                metadata = response_data["metadata"]
                assert metadata["token_type"] == "Slack"
                assert "user" in metadata
                assert metadata["user"]["id"] == "U123456"
    
    @pytest.mark.asyncio
    async def test_get_context_invalid_api_key(self):
        """Test getting context with an invalid API key."""
        # Create a test client that works with async endpoints
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Create a sample request
            request = ContextRequest(
                auth_token="token123",
                token_type="OpenWebUI",
                prompt="What are our Q1 goals?",
                history_summary="Previous conversation about company plans."
            )
            
            # Make the request with an invalid API key
            response = await ac.post(
                "/context",
                json=request.dict(),
                headers={"X-API-Key": "invalid_key"}
            )
            
            # Check response
            assert response.status_code == 401
            response_data = response.json()
            assert "detail" in response_data
            assert "Invalid API key" in response_data["detail"]
    
    @pytest.mark.asyncio
    async def test_get_context_invalid_token(self):
        """Test getting context with an invalid auth token."""
        # Create a test client that works with async endpoints
        async with AsyncClient(app=app, base_url="http://test") as ac:
            # Create an invalid token and request
            request = ContextRequest(
                auth_token="invalid_token",  # Not a valid JWT or Slack token
                token_type="Unknown",  # Unknown token type
                prompt="What are our Q1 goals?",
                history_summary="Previous conversation about company plans."
            )
            
            # Make the request
            response = await ac.post(
                "/context",
                json=request.dict(),
                headers={"X-API-Key": "test_api_key"}
            )
            
            # Check response
            assert response.status_code == 401
            response_data = response.json()
            assert "detail" in response_data
``` 