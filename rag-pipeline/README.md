# RAG Pipeline for Insight Mesh

The RAG (Retrieval-Augmented Generation) Pipeline is a component that enhances LLM responses by retrieving relevant document context from Haystack and injecting it into the conversation.

## Features

- Retrieves relevant documents from Haystack based on user queries
- Extracts user information from JWT tokens for personalized context
- Caches user email lookups in Redis for improved performance
- Integrates with OpenWebUI's PostgreSQL database for user information
- Provides pre-processing hooks for LiteLLM requests

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   - Copy `config/environment.env.example` to `.env` or use environment variables
   - Set database credentials, Redis URL, and other configuration options

3. Test the setup:
   ```bash
   python test_rag_handler.py
   ```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `HAYSTACK_ENDPOINT` | URL of the Haystack search endpoint | `http://haystack:8000/search` |
| `HAYSTACK_MAX_RESULTS` | Maximum number of results to retrieve | `3` |
| `REDIS_ENABLED` | Enable Redis caching | `true` |
| `REDIS_URL` | Redis connection URL | `redis://redis:6379/0` |
| `REDIS_TTL` | Cache TTL in seconds | `3600` (1 hour) |
| `DB_HOST` | PostgreSQL host | `postgres` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | PostgreSQL database name | `openwebui` |
| `DB_USER` | PostgreSQL username | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | `postgres` |
| `DB_USER_TABLE` | Table containing user data | `users` |
| `JWT_SECRET_KEY` | Secret key for JWT verification | `None` (optional) |

## Usage

The `RAGHandler` class is automatically invoked by LiteLLM Proxy for each request, extracting user information from JWT tokens and enhancing requests with relevant document context from Haystack.

Example integration with LiteLLM:

```python
from litellm.proxy import Proxy
from pre_request_hook import rag_handler_instance

# Register the RAG handler with LiteLLM
litellm.register_logger(rag_handler_instance)

# Start the proxy
proxy = Proxy(...)
proxy.start()
```

## How It Works

1. The pre-request hook extracts the JWT token from the Authorization header
2. It decodes the token to get user information (ID and email)
3. If email is not in token, it checks Redis cache or PostgreSQL database
4. It retrieves relevant documents from Haystack based on the user query
5. The context is injected into the system message or a new system message is created
6. The enhanced request is sent to the LLM for response generation 