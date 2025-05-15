import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time
from context_service import ContextService
from models import Document, DocumentMetadata, UserInfo

pytestmark = pytest.mark.asyncio

class TestContextService:
    """Tests for the ContextService class."""
    
    @pytest.fixture
    def mock_es_service(self):
        """Create a mock ElasticsearchService."""
        with patch("context_service.ElasticsearchService") as mock_es:
            # Create a mock instance
            mock_instance = AsyncMock()
            mock_es.return_value = mock_instance
            
            # Set up the search_documents method to return sample documents
            async def mock_search(query, user_email=None, size=5, indices=None):
                return [
                    Document(
                        id="doc1",
                        content="Q1 goals include increasing revenue by 15%",
                        score=0.9,
                        metadata=DocumentMetadata(
                            source="google_drive_files",
                            file_name="Q1_Goals.pdf",
                            is_public=False
                        )
                    ),
                    Document(
                        id="doc2",
                        content="Team objectives for the quarter",
                        score=0.8,
                        metadata=DocumentMetadata(
                            source="slack_messages",
                            is_public=True
                        )
                    )
                ]
            
            mock_instance.search_documents.side_effect = mock_search
            
            # Set up the close method
            async def mock_close():
                return None
            
            mock_instance.close.side_effect = mock_close
            
            yield mock_instance
    
    async def test_get_context_for_prompt_with_user_info(self, mock_es_service):
        """Test getting context with user info."""
        # Create context service
        service = ContextService()
        
        # Create user info
        user_info = UserInfo(
            id="user123",
            email="tmfrisinger@gmail.com",
            name="Test User",
            is_active=True,
            token_type="OpenWebUI"
        )
        
        # Get context
        result = await service.get_context_for_prompt(
            user_id="user123",
            prompt="What are our Q1 goals?",
            history_summary="Previous conversation about company plans.",
            user_info=user_info
        )
        
        # Verify search was called with correct parameters
        mock_es_service.search_documents.assert_called_once()
        call_args = mock_es_service.search_documents.call_args
        
        # Check that the query and user_email are correct
        assert call_args[1]["query"] == "What are our Q1 goals?"
        assert call_args[1]["user_email"] == "tmfrisinger@gmail.com"
        assert call_args[1]["size"] == 5
        
        # Check result
        assert len(result.documents) == 2
        assert result.documents[0].content == "Q1 goals include increasing revenue by 15%"
        assert result.documents[0].source == "google_drive"  # Note: source is modified in the service
        assert result.documents[1].content == "Team objectives for the quarter"
        assert result.documents[1].source == "slack"
        assert result.retrieval_time_ms > 0
        assert result.cache_hit is False
    
    async def test_get_context_for_prompt_without_user_email(self, mock_es_service):
        """Test getting context without user email."""
        # Create context service
        service = ContextService()
        
        # Create user info with no email
        user_info = UserInfo(
            id="user123",
            email=None,  # No email
            name="Test User",
            is_active=True,
            token_type="OpenWebUI"
        )
        
        # Get context
        result = await service.get_context_for_prompt(
            user_id="user123",
            prompt="What are our Q1 goals?",
            history_summary="Previous conversation about company plans.",
            user_info=user_info
        )
        
        # Verify search was not called
        mock_es_service.search_documents.assert_not_called()
        
        # Check result (should be empty)
        assert len(result.documents) == 0
        assert result.retrieval_time_ms > 0
    
    async def test_get_context_for_prompt_with_search_error(self, mock_es_service):
        """Test error handling in get_context_for_prompt."""
        # Set up mock to raise an exception
        mock_es_service.search_documents.side_effect = Exception("Search failed")
        
        # Create context service
        service = ContextService()
        
        # Create user info
        user_info = UserInfo(
            id="user123",
            email="tmfrisinger@gmail.com",
            name="Test User",
            is_active=True,
            token_type="OpenWebUI"
        )
        
        # Get context (should handle the error gracefully)
        result = await service.get_context_for_prompt(
            user_id="user123",
            prompt="What are our Q1 goals?",
            history_summary="Previous conversation about company plans.",
            user_info=user_info
        )
        
        # Check result (should be empty due to error)
        assert len(result.documents) == 0
        assert result.retrieval_time_ms > 0
    
    async def test_close(self, mock_es_service):
        """Test close method."""
        # Create context service
        service = ContextService()
        
        # Call close
        await service.close()
        
        # Verify elasticsearch service close was called
        mock_es_service.close.assert_called_once() 