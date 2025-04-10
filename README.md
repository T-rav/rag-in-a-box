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

2. Configure your OpenAI API key:
   ```bash
   cp .env.example .env
   ```
   Then edit the `.env` file to add your OpenAI API key.

3. Start the services:
   ```bash
   docker-compose up -d
   ```

4. Access the UI at [http://localhost:3000](http://localhost:3000)

### Configuration

- LiteLLM configuration is in `config/litellm_config.yaml`
- By default, the system uses GPT-4 and GPT-4o models

## Development

To customize the RAG pipeline, you can:

1. Modify the Haystack configuration for your specific data sources
2. Create custom retrieval pipelines in the `rag-pipeline` directory
3. Connect your data sources to the system

## License

MIT License - See [LICENSE](LICENSE) for details
