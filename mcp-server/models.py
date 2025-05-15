from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class DocumentMetadata(BaseModel):
    """Metadata for a document returned from Elasticsearch"""
    source: str = Field(default="unknown", description="Source of the document")
    file_name: Optional[str] = Field(default=None, description="File name if applicable")
    created_time: Optional[datetime] = Field(default=None, description="Creation time")
    modified_time: Optional[datetime] = Field(default=None, description="Last modified time")
    web_link: Optional[str] = Field(default=None, description="Web link to the document")
    permissions: List[Dict[str, Any]] = Field(default_factory=list, description="Access permissions")
    is_public: bool = Field(default=False, description="Whether the document is publicly accessible")

class Document(BaseModel):
    """Document model returned from Elasticsearch"""
    id: str = Field(..., description="Document ID")
    content: str = Field(..., description="Document content")
    score: float = Field(..., description="Relevance score")
    metadata: DocumentMetadata = Field(..., description="Document metadata")

class ContextRequest(BaseModel):
    """Request model for context retrieval"""
    auth_token: str = Field(..., description="JWT token for user authentication")
    token_type: str = Field(..., description="Type of JWT token (e.g., OpenWebUI)")
    prompt: str = Field(..., description="User's current prompt")
    history_summary: Optional[str] = Field(None, description="Summary of conversation history")

class ContextItem(BaseModel):
    """A single context item to be injected into the conversation"""
    content: str = Field(..., description="The content to be injected")
    role: str = Field("system", description="The role of the context (system, user, assistant)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about this context item")

class UserInfo(BaseModel):
    """User information extracted from token"""
    id: str = Field(..., description="User ID")
    email: Optional[str] = Field(None, description="User's email address")
    name: Optional[str] = Field(None, description="User's name")
    is_active: bool = Field(True, description="Whether the user is active")
    token_type: str = Field(..., description="Type of authentication token")

class RetrievalMetadata(BaseModel):
    """Metadata about the retrieval process"""
    cache_hit: bool = Field(default=False, description="Whether the result was from cache")
    retrieval_time_ms: int = Field(..., description="Time taken for retrieval in milliseconds")

class ContextSource(BaseModel):
    """Source of context items"""
    type: str = Field(..., description="Type of context source")
    count: int = Field(..., description="Number of items from this source")

class ResponseMetadata(BaseModel):
    """Metadata for context response"""
    user: UserInfo = Field(..., description="User information")
    token_type: str = Field(..., description="Type of JWT token")
    timestamp: str = Field(..., description="ISO format timestamp")
    context_sources: List[ContextSource] = Field(..., description="Sources of context items")
    retrieval_metadata: RetrievalMetadata = Field(..., description="Retrieval performance metrics")

class ContextResponse(BaseModel):
    """Response following the MCP protocol"""
    context_items: List[ContextItem] = Field(..., description="List of context items to be injected into the conversation")
    metadata: ResponseMetadata = Field(..., description="Additional metadata about the context retrieval")

class DocumentResult(BaseModel):
    """Simple document result model for internal use"""
    content: str = Field(..., description="Document content")
    source: str = Field(default="unknown", description="Source of the document")

class ContextResult(BaseModel):
    """Internal context result model"""
    documents: List[DocumentResult] = Field(default_factory=list)
    retrieval_time_ms: int = Field(..., description="Time taken for retrieval in milliseconds")
    cache_hit: bool = Field(default=False, description="Whether the result was from cache") 