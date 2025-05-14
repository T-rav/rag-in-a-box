from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import jwt
from loguru import logger
import os
from dotenv import load_dotenv
from contextvars import ContextVar
from functools import wraps
import time
import json
from context_service import context_service

# Load environment variables
load_dotenv()

# Configure logger to write to both file and console
logger.remove()  # Remove default handler

# Create a context filter class
class ContextFilter:
    """Filter to add context to log records"""
    def __init__(self):
        self.context = {"user_id": "unknown", "token_type": "unknown"}
    
    def __call__(self, record):
        """Add context to log record"""
        record["extra"]["user_id"] = self.context["user_id"]
        record["extra"]["token_type"] = self.context["token_type"]
        return True

# Create and configure the context filter
context_filter = ContextFilter()

# Add handlers with context filter
logger.add(
    "logs/mcp_server.log",
    rotation="100 MB",
    retention="1 week",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[user_id]} | {extra[token_type]} | {message}",
    filter=context_filter
)
logger.add(
    lambda msg: print(msg, end=""),  # Console handler
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[user_id]} | {extra[token_type]} | {message}",
    filter=context_filter
)

# Context variables for logging
request_context = ContextVar("request_context", default={"user_id": None, "token_type": None})

def log_context(user_id: Optional[str] = None, token_type: Optional[str] = None):
    """Update the logging context with user info"""
    current = request_context.get()
    if user_id:
        current["user_id"] = user_id
        context_filter.context["user_id"] = user_id
    if token_type:
        current["token_type"] = token_type
        context_filter.context["token_type"] = token_type
    request_context.set(current)

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

# Add request/response logging middleware
@app.middleware("http")
async def log_requests_middleware(request: Request, call_next):
    # Log request
    request_id = request.headers.get("X-Request-ID", "no-request-id")
    start_time = time.time()
    
    # Get request body if it exists
    body = None
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.json()
        except:
            body = "Could not parse request body"
    
    # Log request details
    logger.info(
        f"Request started | {request.method} {request.url.path} | ID: {request_id} | "
        f"Headers: {dict(request.headers)} | Body: {json.dumps(body) if body else 'No body'}"
    )
    
    try:
        # Process the request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Get response body
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        # Reconstruct response with the body
        response = JSONResponse(
            content=json.loads(response_body) if response_body else None,
            status_code=response.status_code,
            headers=dict(response.headers),
        )
        
        # Patch: Safely log response body
        try:
            body_str = response_body.decode("utf-8")
            try:
                body_json = json.loads(body_str)
                log_body = json.dumps(body_json)
            except Exception:
                log_body = body_str
        except Exception:
            log_body = "<non-decodable bytes>"
        
        logger.info(
            f"Request completed | {request.method} {request.url.path} | ID: {request_id} | "
            f"Status: {response.status_code} | Time: {process_time:.3f}s | "
            f"Response: {log_body}"
        )
        
        return response
    except Exception as e:
        # Log any errors
        logger.error(
            f"Request failed | {request.method} {request.url.path} | ID: {request_id} | "
            f"Error: {str(e)}"
        )
        raise

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
        
        # Handle default token
        if token == "default_token":
            logger.info("Using default token with default email")
            return {
                "user_id": "default_user",
                "email": "tmfrisinger@gmail.com",
                "name": "Default User",
                "is_active": True,
                "token_type": token_type
            }
        
        # For OpenWebUI tokens, we don't verify the signature
        if token_type == "OpenWebUI":
            logger.debug("Decoding OpenWebUI token without signature verification")
            decoded = jwt.decode(token, options={"verify_signature": False})
            logger.debug("Decoded token payload: {}", decoded)
            user_id = decoded.get("sub")
            log_context(user_id=user_id)
            logger.info("Extracted user_id from token")
            if not user_id:
                logger.error("OpenWebUI token missing user_id (sub claim)")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid OpenWebUI token: missing user ID"
                )
            # Instead, always use default user
            decoded["user_id"] = user_id
            decoded["email"] = "tmfrisinger@gmail.com"
            decoded["name"] = "Default User"
            decoded["is_active"] = True
            return decoded
        elif token_type == "Slack":
            if not token.startswith("slack:"):
                logger.error("Invalid Slack token format")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid Slack token format. Expected 'slack:{user_id}'"
                )
            user_id = token.split(":", 1)[1]
            log_context(user_id=user_id)
            logger.info("Extracted Slack user_id from token")
            # Instead, always use default user
            decoded = {
                "user_id": user_id,
                "email": "tmfrisinger@gmail.com",
                "name": "Default User",
                "is_active": True,
                "token_type": "Slack"
            }
            return decoded
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
        # await cache.connect()
        # logger.info("Cache initialized")
        # --- DB pool initialization commented out ---
        # await get_db_pool()
        # logger.info("Database pool initialized")
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
        # await cache.disconnect()
        # logger.info("Cache disconnected")
        # if db_pool:
        #     await db_pool.close()
        #     logger.info("Database pool closed")
        # Close Elasticsearch service
        # await context_service.close()
        # logger.info("Elasticsearch service closed")
        pass
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
        logger.info(f"Processing context request for prompt: {request.prompt[:100]}...")  # Log first 100 chars of prompt
        if request.history_summary:
            logger.debug(f"History summary: {request.history_summary[:200]}...")  # Log first 200 chars of history
        
        # Validate the token and get user info
        user_info = await validate_token(request.auth_token, request.token_type)
        user_id = user_info["user_id"]
        log_context(user_id=user_id)
        logger.info(f"User authenticated: {user_id}")
        
        # Get context for the prompt using ContextService (this will search Elasticsearch)
        context = await context_service.get_context_for_prompt(
            user_id=user_id,
            prompt=request.prompt,
            history_summary=request.history_summary,
            user_info=user_info
        )
        logger.info(f"Context retrieved - Cache hit: {context.get('cache_hit', False)}, "
                   f"Retrieval time: {context.get('retrieval_time_ms', 0)}ms, "
                   f"Documents: {len(context.get('documents', []))}")
        
        context_items = []
        # Add system context if present
        if context.get("system_context"):
            logger.debug("Adding system context to response")
            context_items.append(ContextItem(
                content=context["system_context"],
                role="system",
                metadata={"source": "system_context"}
            ))
        # Add document contexts
        for doc in context.get("documents", []):
            context_items.append(ContextItem(
                content=doc["content"],
                role="system",
                metadata={"source": doc.get("source", "document")}
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
                "context_sources": [
                    {"type": "documents", "count": len(context.get("documents", []))}
                ],
                "retrieval_metadata": {
                    "cache_hit": bool(context.get("cache_hit", False)),
                    "retrieval_time_ms": context.get("retrieval_time_ms", 0)
                }
            }
        )
        logger.info(f"Returning response with {len(context_items)} context items")
        return response
        
    except Exception as e:
        logger.error(f"Error processing context request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing context request: {str(e)}"
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