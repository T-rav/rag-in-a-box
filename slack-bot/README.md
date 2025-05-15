# Insight Mesh Slack AI Bot

A Slack bot for Insight Mesh that leverages Slack's new AI Apps features to provide a better user experience.

## Features

- **AI Apps Integration**: Uses Slack's new AI Apps interface for improved discoverability and user experience
- **Threading Support**: Automatically manages conversation threads
- **Status Indicators**: Shows loading states while generating responses
- **Suggested Prompts**: Provides helpful prompt suggestions to guide users
- **RAG Integration**: Connects to your LLM API for Retrieval-Augmented Generation

## Quick Start

1. Follow the setup instructions in [SETUP.md](SETUP.md) to configure your Slack app
2. Create a `.env` file with the following variables:
   ```
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_APP_TOKEN=xapp-your-app-token
   LLM_API_URL=http://your-llm-api-url
   LLM_API_KEY=your-llm-api-key
   LLM_MODEL=gpt-4
   ```
3. Run the bot:
   ```bash
   ./run_local.sh
   ```
   
## Docker Deployment

Build and run the Docker container:

```bash
docker build -t insight-mesh-slack-bot .
docker run -d --env-file .env --name insight-mesh-bot insight-mesh-slack-bot
```

## Architecture

The bot is built using:
- **slack-bolt**: Slack's official Python framework for building Slack apps
- **aiohttp**: Asynchronous HTTP client/server for Python
- **LiteLLM Proxy**: Compatible with OpenAI's API for connecting to different LLM providers

## Development

- **app_ai.py**: Main application with AI Apps support
- **app.py**: Legacy application (kept for reference)
- **requirements.txt**: Python dependencies
- **SETUP.md**: Configuration guide for Slack app settings

## Troubleshooting

If you're experiencing issues:

1. Ensure all Slack app permissions and event subscriptions are configured correctly
2. Check that your environment variables are set correctly
3. Verify your LLM API is accessible from the bot
4. Look for error messages in the bot logs

## Notes About Socket Mode

While this implementation still uses Socket Mode for development convenience, we recommend:

1. Using Socket Mode during development for easy testing
2. Switching to HTTP endpoints for production deployments by:
   - Disabling Socket Mode in your Slack app settings
   - Setting up a public HTTP endpoint for your bot
   - Updating your app to use that endpoint instead of Socket Mode 