#  RAG in a Box

RAG stack for chat bots that aims to be a deploy, configure and go solution. 

## Components

🧠 OpenWebUI  -> The chat UI because why not!  
🔄 LiteLLM Proxy	-> Monitor, Observe and Managae LLMOps centrally - make use of LangFuse to handle prompt managment     
📚 RAG Pipeline	Python (your code) -> Custom RAG injection code loaded dynamically like a plugin _(Inject company data, do auth checks, add guardrails to make it safe and prod ready)_   
🔍 Haystack	-> Data and agents layer for building powerful search and retrieval systems
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
   git clone --recurse-submodules https://github.com/yourusername/rag-in-a-box.git
   cd rag-in-a-box
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

4. Access the UI at [http://localhost](http://localhost) (secured with Google authentication)

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
   http://localhost/auth/oauth2/google/authorization-code-callback
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

1. Modify the Haystack configuration for your specific data sources
2. Create custom retrieval pipelines in the `rag-pipeline` directory
3. Connect your data sources to the system

## License

MIT License - See [LICENSE](LICENSE) for details
