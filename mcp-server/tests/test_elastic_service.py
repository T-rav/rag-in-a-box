import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
import os
from elasticsearch import AsyncElasticsearch
from elastic_service import ElasticsearchService
from models import Document

pytestmark = pytest.mark.asyncio

class TestElasticsearchService:
    """Tests for the ElasticsearchService class."""
    
    @pytest.fixture
    def mock_es_client(self):
        """Create a mock Elasticsearch client."""
        with patch("elastic_service.AsyncElasticsearch") as mock_es:
            # Create a mock instance
            mock_instance = AsyncMock()
            mock_es.return_value = mock_instance
            
            # Set up search response
            search_response = {
                "hits": {
                    "total": {"value": 2},
                    "hits": [
                        {
                            "_id": "doc1",
                            "_score": 0.9,
                            "_source": {
                                "content": "Q1 goals include increasing revenue by 15%",
                                "meta": {
                                    "source": "google_drive_files",
                                    "file_name": "Q1_Goals.pdf",
                                    "created_time": "2023-01-01T00:00:00",
                                    "modified_time": "2023-01-15T00:00:00",
                                    "web_link": "https://drive.google.com/file/abc123",
                                    "permissions": [
                                        {"type": "user", "email": "tmfrisinger@gmail.com"}
                                    ],
                                    "is_public": False
                                }
                            }
                        },
                        {
                            "_id": "doc2",
                            "_score": 0.8,
                            "_source": {
                                "content": "Team objectives for the quarter",
                                "meta": {
                                    "source": "slack_messages",
                                    "is_public": True
                                }
                            }
                        }
                    ]
                }
            }
            
            # Set up the mock response object
            mock_response = MagicMock()
            mock_response.body = search_response
            mock_instance.search.return_value = mock_response
            
            yield mock_instance
    
    async def test_search_documents_with_email(self, mock_es_client):
        """Test searching documents with user email filtering."""
        # Create service with mock client
        service = ElasticsearchService()
        
        # Perform search with user email
        results = await service.search_documents(
            query="Q1 goals",
            user_email="tmfrisinger@gmail.com",
            size=5
        )
        
        # Verify search was called with correct parameters
        mock_es_client.search.assert_called_once()
        call_args = mock_es_client.search.call_args[1]
        
        # Check that the index is correct
        assert call_args["index"] == "google_drive_files,slack_messages,web_pages"
        
        # Check that the query includes permission filtering
        body = call_args["body"]
        assert "bool" in body["query"]
        assert "should" in body["query"]["bool"]
        
        # Check that user email is in the permission filter
        should_clauses = body["query"]["bool"]["should"]
        email_clause = [c for c in should_clauses if c.get("term", {}).get("meta.accessible_by_emails.keyword")]
        assert len(email_clause) == 1
        assert email_clause[0]["term"]["meta.accessible_by_emails.keyword"] == "tmfrisinger@gmail.com"
        
        # Check that domain filtering is included
        domain_clause = [c for c in should_clauses if c.get("term", {}).get("meta.accessible_by_domains.keyword")]
        assert len(domain_clause) == 1
        assert domain_clause[0]["term"]["meta.accessible_by_domains.keyword"] == "gmail.com"
        
        # Check that minimum_should_match is set
        assert body["query"]["bool"]["minimum_should_match"] == 1
        
        # Check results
        assert len(results) == 2
        assert results[0].id == "doc1"
        assert results[0].content == "Q1 goals include increasing revenue by 15%"
        assert results[0].score == 0.9
        assert results[0].metadata.source == "google_drive_files"
        assert results[0].metadata.file_name == "Q1_Goals.pdf"
        assert results[0].metadata.is_public is False
        
        assert results[1].id == "doc2"
        assert results[1].content == "Team objectives for the quarter"
        assert results[1].score == 0.8
        assert results[1].metadata.source == "slack_messages"
        assert results[1].metadata.is_public is True
    
    async def test_search_documents_without_email(self, mock_es_client):
        """Test searching documents without user email (no permission filtering)."""
        # Create service with mock client
        service = ElasticsearchService()
        
        # Perform search without user email
        results = await service.search_documents(
            query="Q1 goals",
            user_email=None,
            size=5
        )
        
        # Verify search was called with correct parameters
        mock_es_client.search.assert_called_once()
        call_args = mock_es_client.search.call_args[1]
        
        # Check that the index is correct
        assert call_args["index"] == "google_drive_files,slack_messages,web_pages"
        
        # Check that the query does not include permission filtering
        body = call_args["body"]
        assert "multi_match" in body["query"]
        assert body["query"]["multi_match"]["query"] == "Q1 goals"
        
        # Check results
        assert len(results) == 2
    
    async def test_search_documents_error_handling(self, mock_es_client):
        """Test error handling in search_documents."""
        # Set up mock to raise an exception
        mock_es_client.search.side_effect = Exception("Search failed")
        
        # Create service with mock client
        service = ElasticsearchService()
        
        # Verify that the exception is raised
        with pytest.raises(Exception) as exc_info:
            await service.search_documents(
                query="Q1 goals",
                user_email="tmfrisinger@gmail.com"
            )
        
        assert str(exc_info.value) == "Search failed"
    
    async def test_close(self, mock_es_client):
        """Test close method."""
        # Create service with mock client
        service = ElasticsearchService()
        
        # Call close
        await service.close()
        
        # Verify close was called
        mock_es_client.close.assert_called_once() 