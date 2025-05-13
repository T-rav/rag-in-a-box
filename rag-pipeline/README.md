# RAG Pipeline for Insight Mesh

The RAG (Retrieval-Augmented Generation) Pipeline is a component that enhances LLM responses by retrieving relevant context from the MCP (Message Context Provider) server and injecting it into the conversation.

## Features

- Retrieves relevant context from MCP server based on user queries and conversation history
- Passes JWT tokens to MCP server for user authentication and context personalization
- Provides pre-processing hooks for LiteLLM requests
- Supports different token types (e.g., OpenWebUI)

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure environment variables:
   - Copy `config/environment.env.example` to `.env` or use environment variables
   - Set MCP server configuration and token type

3. Test the setup:
   ```bash
   python test_rag_handler.py
   ```

## Configuration Options

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_SERVER_URL` | URL of the MCP server endpoint | `http://mcp:8000` |
| `MCP_API_KEY` | API key for MCP server authentication | `` |
| `MCP_TIMEOUT` | Timeout for MCP server requests in seconds | `30` |
| `MCP_MAX_RETRIES` | Maximum number of retries for MCP requests | `3` |
| `TOKEN_TYPE` | Type of JWT token being used (e.g., OpenWebUI) | `OpenWebUI` |

## Usage

The `RAGHandler` class is automatically invoked by LiteLLM Proxy for each request, passing the JWT token to the MCP server for context retrieval.

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
2. It sends the token, token type, prompt, and conversation history to the MCP server
3. The MCP server handles user authentication and context retrieval
4. The context is injected into the system message or a new system message is created
5. The enhanced request is sent to the LLM for response generation

## MCP Server Integration

The RAG pipeline communicates with the MCP server using a REST API. For each request, it sends:

- JWT token (for user authentication and context personalization)
- Token type (e.g., OpenWebUI)
- Current prompt
- Conversation history summary (last 5 messages)
- API key for authentication

The MCP server should:
1. Validate and decode the JWT token
2. Extract user information based on the token type
3. Retrieve relevant context based on the user and query
4. Return a JSON object containing the context to be injected into the conversation

Example MCP server request:
```json
{
  "auth_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "OpenWebUI",
  "prompt": "What are our Q1 goals?",
  "history_summary": "user: Hi\nassistant: Hello! How can I help you today?"
}
``` 