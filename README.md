# Insight Mesh

Search everything. Act on anything. Build smarter AI. A RAG stack that helps organizations unlock the value of their internal knowledge by turning search into a springboard for smarter automation—through chat, agent workflows, and direct access.

Visit our website at [https://insightmesh.koderex.dev/](https://insightmesh.koderex.dev/) for more information about the project.

## Components

🧠 OpenWebUI  -> The chat UI because why not!  
🔄 LiteLLM Proxy	-> Monitor, Observe and Manage LLMOps centrally - make use of LangFuse to handle prompt management     
📊 Dagster -> ETL and scheduling engine for data ingestion and pipeline orchestration  
📚 RAG Pipeline	Python (your code) -> Custom RAG injection code loaded dynamically like a plugin _(Inject company data, do auth checks, add guardrails to make it safe and prod ready)_   
🔍 Elasticsearch & Neo4j -> Data and agents layer for building powerful search and retrieval systems  
🛡️ Caddy	Static binary (Go)	-> Auth Proxy to allow OpenWebUI and LiteLLM to centralize auth  

**All you need to do is build the data pipelines to ingest and index**

## Quick Start

### Prerequisites

- Git
- Docker and Docker Compose
- OpenAI API key

### Setup

1. Clone the repository with submodules:
   ```bash
   git clone --recurse-submodules https://github.com/yourusername/insight-mesh.git
   cd insight-mesh
   ```

   If you've already cloned without submodules:
   ```bash
   git submodule init
   git submodule update
   ```

2. Configure your environment variables:
   ```bash
   cp .env.example .env
   ```
   Then edit the `.env` file to add your OpenAI API key and Google OAuth credentials.
   
   Alternatively, use the setup script to configure Google authentication:
   ```bash
   chmod +x setup-google-auth.sh
   ./setup-google-auth.sh
   ```

3. Start the services:
   ```bash
   docker-compose up -d
   ```

4. Access the UI at [http://localhost:8080](http://localhost:8080) (secured with Google authentication)

### Configuration

- LiteLLM configuration is in `config/litellm_config.yaml`
- By default, the system uses GPT-4 and GPT-4o models
- Caddy configuration for Google authentication is in `config/caddy/Caddyfile`

### Google Authentication Setup

To set up Google OAuth for authentication:

1. Visit the [Google Cloud Console](https://console.cloud.google.com/apis/credentials) to create OAuth credentials
2. Create an OAuth 2.0 Client ID (Web application type)
3. Add the following as an authorized redirect URI:
   ```
   http://localhost:8080/auth/oauth2/google/authorization-code-callback
   ```
4. Copy your Client ID and Client Secret to the `.env` file or use the setup script
5. By default, only users with email addresses from the specified domain (default: gmail.com) will be allowed access

#### Environment Variables

| Variable | Description | Default |
|----------|-------------|--------|
| `OPENAI_API_KEY` | Your OpenAI API key | - |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | - |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | - |
| `DOMAIN` | Domain for your deployment | localhost |
| `ALLOWED_EMAIL_DOMAIN` | Email domain allowed for authentication | gmail.com |

## Development

To customize the RAG pipeline, you can:

1. Configure Dagster assets for your ETL workflows and scheduling needs
2. Modify the Elasticsearch and Neo4j configurations for your specific data sources
3. Create custom retrieval pipelines in the `rag-pipeline` directory
4. Connect your data sources to the system (currently supports Google Drive, with more integrations coming soon)

## Data Sources

### Google Drive Integration
- Supports indexing of Google Docs, Sheets, and Slides
- Maintains folder hierarchy in Neo4j
- Handles permissions and access control
- Automatic content updates through scheduled indexing

## License

MIT License - See [LICENSE](LICENSE) for details
