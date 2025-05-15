import os
import sys
import pytest
import asyncio
from faker import Faker
from datetime import datetime
import jwt

# Add the parent directory to the path so we can import the application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Import application modules
from models import (
    Document, 
    DocumentMetadata, 
    UserInfo, 
    ContextRequest, 
    DocumentResult, 
    ContextResult
)
from elastic_service import ElasticsearchService
from context_service import ContextService

# Initialize faker for generating test data
fake = Faker()

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def sample_document():
    """Generate a sample document for testing."""
    return Document(
        id=fake.uuid4(),
        content=fake.paragraph(nb_sentences=5),
        score=0.95,
        metadata=DocumentMetadata(
            source="google_drive",
            file_name=f"{fake.word()}.pdf",
            created_time=datetime.now(),
            modified_time=datetime.now(),
            web_link=fake.uri(),
            permissions=[{"type": "user", "email": "tmfrisinger@gmail.com"}],
            is_public=False
        )
    )

@pytest.fixture
def sample_user_info():
    """Generate sample user info for testing."""
    return UserInfo(
        id=fake.uuid4(),
        email="tmfrisinger@gmail.com",
        name=fake.name(),
        is_active=True,
        token_type="OpenWebUI"
    )

@pytest.fixture
def sample_context_request(sample_user_info):
    """Generate a sample context request for testing."""
    # Create a JWT token for the sample user
    token_payload = {
        "sub": sample_user_info.id,
        "email": sample_user_info.email,
        "name": sample_user_info.name,
        "exp": datetime.now().timestamp() + 3600  # 1 hour expiration
    }
    token = jwt.encode(token_payload, "test_secret_key", algorithm="HS256")
    
    return ContextRequest(
        auth_token=token,
        token_type="OpenWebUI",
        prompt="What are the Q1 goals for our company?",
        history_summary="User asked about company projects."
    )

@pytest.fixture
def sample_document_results():
    """Generate sample document results for testing."""
    return [
        DocumentResult(
            content=fake.paragraph(nb_sentences=3),
            source="google_drive"
        ),
        DocumentResult(
            content=fake.paragraph(nb_sentences=3),
            source="slack"
        ),
        DocumentResult(
            content=fake.paragraph(nb_sentences=3),
            source="web"
        )
    ]

@pytest.fixture
def sample_context_result(sample_document_results):
    """Generate a sample context result for testing."""
    return ContextResult(
        documents=sample_document_results,
        retrieval_time_ms=150,
        cache_hit=False
    )

@pytest.fixture
def mock_elasticsearch_service(mocker):
    """Create a mock ElasticsearchService for testing."""
    mock_service = mocker.patch("elastic_service.ElasticsearchService", autospec=True)
    mock_instance = mock_service.return_value
    
    # Set up the search_documents method to return sample documents
    async def mock_search(*args, **kwargs):
        return [
            Document(
                id=fake.uuid4(),
                content=fake.paragraph(),
                score=0.95,
                metadata=DocumentMetadata(
                    source="google_drive",
                    is_public=False,
                    permissions=[{"type": "user", "email": kwargs.get("user_email", "tmfrisinger@gmail.com")}]
                )
            ),
            Document(
                id=fake.uuid4(),
                content=fake.paragraph(),
                score=0.85,
                metadata=DocumentMetadata(
                    source="slack",
                    is_public=True
                )
            )
        ]
    
    mock_instance.search_documents.side_effect = mock_search
    
    # Set up the close method
    async def mock_close():
        return None
    
    mock_instance.close.side_effect = mock_close
    
    return mock_instance

@pytest.fixture
def mock_context_service(mocker, sample_context_result):
    """Create a mock ContextService for testing."""
    mock_service = mocker.patch("context_service.ContextService", autospec=True)
    mock_instance = mock_service.return_value
    
    # Set up the get_context_for_prompt method to return a sample result
    async def mock_get_context(*args, **kwargs):
        return sample_context_result
    
    mock_instance.get_context_for_prompt.side_effect = mock_get_context
    
    # Set up the close method
    async def mock_close():
        return None
    
    mock_instance.close.side_effect = mock_close
    
    return mock_instance 