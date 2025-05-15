# Message Context Provider (MCP) Server

The MCP server is a component that provides context-aware responses for LLM conversations. It follows the MCP protocol for context retrieval and injection.

## Features

- JWT token validation and user authentication
- Context retrieval based on user queries and conversation history
- User and conversation management
- Caching with Redis for improved performance
- PostgreSQL database for persistent storage
- FastAPI-based REST API
- MCP protocol compliance

## MCP Protocol

The server implements the Message Context Provider (MCP) protocol, which defines how context is retrieved and injected into conversations.

### Request Format

```json
{
  "auth_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "OpenWebUI",
  "prompt": "What are our Q1 goals?",
  "history_summary": "user: Hi\nassistant: Hello! How can I help you today?"
}
```

### Response Format

```json
{
  "context_items": [
    {
      "content": "You are a helpful assistant that provides context-aware responses.",
      "role": "system",
      "metadata": {
        "source": "system_context"
      }
    },
    {
      "content": "This is a sample document about Q1 goals.",
      "role": "system",
      "metadata": {
        "source": "document",
        "document_id": "doc1",
        "relevance_score": 0.95
      }
    },
    {
      "content": "Previous conversation context",
      "role": "system",
      "metadata": {
        "source": "conversation_history"
      }
    }
  ],
  "metadata": {
    "user": {
      "id": "123",
      "email": "user@example.com",
      "name": "John Doe"
    },
    "token_type": "OpenWebUI",
    "timestamp": "2024-01-20T12:00:00Z",
    "conversation_id": 456,
    "context_sources": [
      {
        "type": "recent_contexts",
        "count": 2
      },
      {
        "type": "conversations",
        "count": 1
      }
    ],
    "retrieval_metadata": {
      "cache_hit": false,
      "retrieval_time_ms": 150
    }
  }
}
```

### Context Items

Each context item in the response represents a piece of context to be injected into the conversation:

- `content`: The actual content to be injected
- `role`: The role of the context (system, user, assistant)
- `metadata`: Additional information about the context item

### Metadata

The response metadata includes:

- User information
- Token type
- Timestamp
- Conversation ID
- Context sources
- Retrieval performance metrics

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   ```bash
   # Copy the example env file
   cp .env.example .env
   
   # Edit the environment variables
   MCP_API_KEY=your_api_key_here
   JWT_SECRET_KEY=your_jwt_secret_here
   DB_URL=postgresql+asyncpg://user:password@localhost:5432/dbname
   REDIS_URL=redis://localhost:6379/0
   ```

3. Initialize the database:
   ```bash
   # The database will be automatically initialized on server startup
   # or you can run the initialization script
   python -c "from database import init_db; import asyncio; asyncio.run(init_db())"
   ```

4. Start the server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

## API Endpoints

### POST /context

Retrieve context for a user's prompt.

Request:
```json
{
  "auth_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "OpenWebUI",
  "prompt": "What are our Q1 goals?",
  "history_summary": "user: Hi\nassistant: Hello! How can I help you today?"
}
```

Response:
```json
{
  "context": {
    "user_id": "123",
    "timestamp": "2024-01-20T12:00:00Z",
    "prompt": "What are our Q1 goals?",
    "context_type": "placeholder",
    "sources": [
      {
        "type": "recent_contexts",
        "count": 2
      },
      {
        "type": "conversations",
        "count": 1
      }
    ],
    "metadata": {
      "history_summary": "user: Hi\nassistant: Hello! How can I help you today?"
    }
  },
  "metadata": {
    "user": {
      "id": "123",
      "email": "user@example.com",
      "name": "John Doe"
    },
    "token_type": "OpenWebUI",
    "timestamp": "2024-01-20T12:00:00Z"
  }
}
```

### GET /health

Health check endpoint.

Response:
```json
{
  "status": "healthy"
}
```

## Database Schema

### Users
- `id` (String, Primary Key): User ID from JWT token
- `email` (String, Unique): User's email address
- `name` (String): User's name
- `created_at` (DateTime): Account creation timestamp
- `updated_at` (DateTime): Last update timestamp
- `is_active` (Boolean): Account status
- `metadata` (JSON): Additional user metadata

### Contexts
- `id` (Integer, Primary Key): Context ID
- `user_id` (String, Foreign Key): Reference to users table
- `content` (JSON): Context content
- `created_at` (DateTime): Creation timestamp
- `expires_at` (DateTime): Expiration timestamp
- `is_active` (Boolean): Context status
- `metadata` (JSON): Additional context metadata

### Conversations
- `id` (Integer, Primary Key): Conversation ID
- `user_id` (String, Foreign Key): Reference to users table
- `title` (String): Conversation title
- `created_at` (DateTime): Creation timestamp
- `updated_at` (DateTime): Last update timestamp
- `is_active` (Boolean): Conversation status
- `metadata` (JSON): Additional conversation metadata

### Messages
- `id` (Integer, Primary Key): Message ID
- `conversation_id` (Integer, Foreign Key): Reference to conversations table
- `role` (String): Message role (user, assistant, system)
- `content` (String): Message content
- `created_at` (DateTime): Creation timestamp
- `metadata` (JSON): Additional message metadata

## Caching

The server uses Redis for caching:
- User information
- Context retrieval results
- Conversation history

Cache TTL is configurable via the `CACHE_TTL` environment variable (default: 1 hour).

## Development

1. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. Run tests:
   ```bash
   ./run_tests.sh
   ```
   
   Or manually:
   ```bash
   python -m pytest tests/ -v --cov=. --cov-report=term-missing
   ```

3. Run linting:
   ```bash
   flake8
   black .
   ```

## Testing

The MCP server has a comprehensive test suite covering all major components:

- **ElasticsearchService**: Tests for proper querying with user permission filtering
- **ContextService**: Tests for context retrieval and handling of various scenarios
- **API Endpoints**: Tests for API functionality, authentication, and error handling

### Test Structure

```
mcp-server/
├── tests/
│   ├── conftest.py           # Common fixtures and test setup
│   ├── test_elastic_service.py  # Tests for Elasticsearch service
│   ├── test_context_service.py  # Tests for Context service
│   └── test_main.py          # Tests for API endpoints
```

### Test Coverage

The tests aim to cover:

- Authentication and authorization flows
- Context retrieval with proper permission filtering
- Error handling and edge cases
- Response formatting according to the MCP protocol

### Setting Up for Testing

1. Create a virtual environment (if not already created):
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

### Running Tests

To run all tests:
```bash
./run_tests.sh
```

To run a specific test file:
```bash
python -m pytest tests/test_elastic_service.py -v
```

To run a specific test:
```bash
python -m pytest tests/test_elastic_service.py::TestElasticsearchService::test_search_documents_with_email -v
```

### Running Tests with Coverage

To run tests with coverage reporting:
```bash
python -m pytest tests/ -v --cov=. --cov-report=term-missing
```

This will show which lines of code are covered by the tests and which are not.

## Docker Support

Build and run with Docker:

```bash
# Build the image
docker build -t mcp-server .

# Run the container
docker run -p 8000:8000 --env-file .env mcp-server
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_API_KEY` | API key for server authentication | (required) |
| `JWT_SECRET_KEY` | Secret key for JWT verification | (required) |
| `DB_URL` | PostgreSQL connection URL | `postgresql+asyncpg://postgres:postgres@localhost:5432/openwebui` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| `CACHE_TTL` | Cache TTL in seconds | `3600` |
| `MAX_RETRIES` | Maximum number of retries for operations | `3` | 