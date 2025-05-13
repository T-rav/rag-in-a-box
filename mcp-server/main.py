from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import jwt
from loguru import logger
import os
from dotenv import load_dotenv
from context_service import context_service
from cache import cache
import asyncpg
import uvicorn
from uvicorn.protocols.fcgi import FCGIProtocol
from contextvars import ContextVar
from functools import wraps

# Load environment variables
load_dotenv()

# Context variables for logging
request_context = ContextVar("request_context", default={"user_id": None, "token_type": None})

def log_context(user_id: Optional[str] = None, token_type: Optional[str] = None):
    """Update the logging context with user info"""
    current = request_context.get()
    if user_id:
        current["user_id"] = user_id
    if token_type:
        current["token_type"] = token_type
    request_context.set(current)

# Configure logger to include context
logger.configure(
    extra={
        "user_id": lambda: request_context.get()["user_id"],
        "token_type": lambda: request_context.get()["token_type"]
    }
)

# Initialize FastAPI app
app = FastAPI(
    title="Message Context Provider (MCP) Server",
    description="Server for providing context-aware responses based on user queries and conversation history",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class ContextRequest(BaseModel):
    auth_token: str = Field(..., description="JWT token for user authentication")
    token_type: str = Field(..., description="Type of JWT token (e.g., OpenWebUI)")
    prompt: str = Field(..., description="User's current prompt")
    history_summary: Optional[str] = Field(None, description="Summary of conversation history")

class ContextItem(BaseModel):
    """A single context item to be injected into the conversation"""
    content: str = Field(..., description="The content to be injected")
    role: str = Field("system", description="The role of the context (system, user, assistant)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about this context item")

class ContextResponse(BaseModel):
    """Response following the MCP protocol"""
    context_items: List[ContextItem] = Field(..., description="List of context items to be injected into the conversation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata about the context retrieval")

# Configuration
class Settings:
    MCP_API_KEY: str = os.getenv("MCP_API_KEY", "")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour default
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    OPENWEBUI_DB_URL: str = os.getenv("OPENWEBUI_DB_URL", "postgresql://postgres:postgres@postgres:5432/openwebui")

settings = Settings()

# Database connection pool
db_pool = None

async def get_db_pool():
    """Get or create database connection pool"""
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(settings.OPENWEBUI_DB_URL)
    return db_pool

# Dependencies
async def verify_api_key(x_api_key: str = Header(...)) -> None:
    """Verify the API key from the request header"""
    if x_api_key != settings.MCP_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

async def validate_token(token: str, token_type: str) -> Dict[str, Any]:
    """Validate and decode the JWT token"""
    try:
        log_context(token_type=token_type)
        logger.info("Validating token")
        
        # For OpenWebUI tokens, we don't verify the signature
        if token_type == "OpenWebUI":
            logger.debug("Decoding OpenWebUI token without signature verification")
            decoded = jwt.decode(token, options={"verify_signature": False})
            logger.debug("Decoded token payload: {}", decoded)
            
            # For OpenWebUI, we need to look up the user in the database
            user_id = decoded.get("sub")  # OpenWebUI uses 'sub' for user ID
            log_context(user_id=user_id)
            logger.info("Extracted user_id from token")
            
            if not user_id:
                logger.error("OpenWebUI token missing user_id (sub claim)")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid OpenWebUI token: missing user ID"
                )
                
            # Look up user in OpenWebUI database
            logger.info("Looking up user in OpenWebUI database")
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                user = await conn.fetchrow(
                    "SELECT id, email, name, is_active FROM users WHERE id = $1",
                    user_id
                )
                
                if not user:
                    logger.error("User not found in OpenWebUI database")
                    raise HTTPException(
                        status_code=404,
                        detail="User not found in OpenWebUI database"
                    )
                    
                logger.info("Found user in database: email={}, name={}, active={}", 
                          user["email"], user["name"], user["is_active"])
                
                # Add user info to the decoded token
                decoded["user_id"] = user["id"]
                decoded["email"] = user["email"]
                decoded["name"] = user["name"]
                decoded["is_active"] = user["is_active"]
                
        elif token_type == "Slack":
            # For Slack tokens, we expect format "slack:{user_id}"
            if not token.startswith("slack:"):
                logger.error("Invalid Slack token format")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid Slack token format. Expected 'slack:{user_id}'"
                )
                
            user_id = token.split(":", 1)[1]
            log_context(user_id=user_id)
            logger.info("Extracted Slack user_id from token")
            
            # Look up user in Slack users table
            logger.info("Looking up user in Slack users table")
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                user = await conn.fetchrow(
                    """
                    SELECT slack_id, email, real_name, display_name 
                    FROM slack_users 
                    WHERE slack_id = $1
                    """,
                    user_id
                )
                
                if not user:
                    logger.error("User not found in Slack users table")
                    raise HTTPException(
                        status_code=404,
                        detail="User not found in Slack users table"
                    )
                    
                logger.info("Found Slack user in database: email={}, name={}", 
                          user["email"], user["real_name"])
                
                # Create decoded token with user info
                decoded = {
                    "user_id": user["slack_id"],
                    "email": user["email"],
                    "name": user["real_name"] or user["display_name"],
                    "is_active": True,  # Slack users are always active if they exist
                    "token_type": "Slack"
                }
                
        else:
            logger.info("Validating token with signature verification")
            decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
            logger.debug("Decoded token payload: {}", decoded)
            
            user_id = decoded.get("sub") or decoded.get("id")
            log_context(user_id=user_id)
            logger.info("Extracted user_id from token")
            
            if not user_id:
                logger.error("Token missing user ID")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token: missing user ID"
                )
            decoded["user_id"] = user_id
        
        logger.info("Token validation successful")
        return decoded
        
    except jwt.InvalidTokenError as e:
        logger.error("Invalid token error: {}", str(e))
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )
    except Exception as e:
        logger.error("Error validating token: {}", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error processing token"
        )

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Initialize cache
        await cache.connect()
        logger.info("Cache initialized")
        
        # Initialize database pool
        await get_db_pool()
        logger.info("Database pool initialized")
        
        # Initialize Elasticsearch service
        # Note: The Elasticsearch service is initialized in the ContextService
        logger.info("Services initialized")
    except Exception as e:
        logger.error("Error during startup: {}", str(e))
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    try:
        await cache.disconnect()
        logger.info("Cache disconnected")
        
        if db_pool:
            await db_pool.close()
            logger.info("Database pool closed")
            
        # Close Elasticsearch service
        await context_service.close()
        logger.info("Elasticsearch service closed")
    except Exception as e:
        logger.error("Error during shutdown: {}", str(e))

@app.post("/context", response_model=ContextResponse)
async def get_context(
    request: ContextRequest,
    _: None = Depends(verify_api_key)
) -> ContextResponse:
    """
    Retrieve context based on the user's token, prompt, and conversation history.
    The context is personalized based on the user's identity and the current conversation.
    """
    try:
        log_context(token_type=request.token_type)
        logger.info("Received context request")
        logger.debug("Request prompt: {}", request.prompt)
        if request.history_summary:
            logger.debug("History summary: {}", request.history_summary)
            
        # Validate the token and get user info
        user_info = await validate_token(request.auth_token, request.token_type)
        user_id = user_info["user_id"]  # We ensure this is set in validate_token
        log_context(user_id=user_id)
        logger.info("Processing request")
        
        # Get context for the prompt
        logger.info("Retrieving context for prompt")
        context = await context_service.get_context_for_prompt(
            user_id=user_id,
            prompt=request.prompt,
            history_summary=request.history_summary,
            user_info=user_info  # Pass full user info for context generation
        )
        logger.debug("Retrieved context: {}", context)
        
        # Transform the context into MCP protocol format
        context_items = []
        
        # Add system context if available
        if context.get("system_context"):
            logger.debug("Adding system context")
            context_items.append(ContextItem(
                content=context["system_context"],
                role="system",
                metadata={"source": "system_context"}
            ))
            
        # Add relevant documents if available
        if context.get("documents"):
            logger.debug("Adding {} documents", len(context["documents"]))
            for doc in context["documents"]:
                context_items.append(ContextItem(
                    content=doc["content"],
                    role="system",
                    metadata={
                        "source": "document",
                        "document_id": doc.get("id"),
                        "relevance_score": doc.get("score")
                    }
                ))
                
        # Add conversation history if available
        if context.get("conversation_history"):
            logger.debug("Adding {} conversation history items", len(context["conversation_history"]))
            for msg in context["conversation_history"]:
                context_items.append(ContextItem(
                    content=msg["content"],
                    role=msg["role"],
                    metadata={"source": "conversation_history"}
                ))
                
        # If no specific context items were found, add a default system message
        if not context_items:
            logger.info("No context items found, adding default system message")
            context_items.append(ContextItem(
                content="I am a helpful assistant. I will provide context-aware responses based on your queries.",
                role="system",
                metadata={"source": "default"}
            ))
        
        response = ContextResponse(
            context_items=context_items,
            metadata={
                "user": {
                    "id": user_id,
                    "email": user_info.get("email"),
                    "name": user_info.get("name")
                },
                "token_type": request.token_type,
                "timestamp": datetime.utcnow().isoformat(),
                "context_sources": context.get("sources", []),
                "retrieval_metadata": {
                    "cache_hit": bool(context.get("cache_hit", False)),
                    "retrieval_time_ms": context.get("retrieval_time_ms", 0)
                }
            }
        )
        logger.info("Returning response with {} context items", len(context_items))
        logger.debug("Response metadata: {}", response.metadata)
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing context request: {}", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while processing context request"
        )
    finally:
        # Clear the context at the end of the request
        request_context.set({"user_id": None, "token_type": None})

@app.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint"""
    return {"status": "healthy"}

if __name__ == "__main__":
    config = uvicorn.Config(
        "main:app",
        host="0.0.0.0",
        port=9090,
        http="fcgi",
        protocol_factory=FCGIProtocol
    )
    server = uvicorn.Server(config)
    server.run() 