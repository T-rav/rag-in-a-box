# Slack AI App Setup Guide

This guide will help you configure your Slack app to use the new AI Apps features.

## Step 1: Update App Configuration in Slack

1. Go to [Slack API Apps page](https://api.slack.com/apps) and select your bot application
2. Navigate to "Agents & AI Apps" in the left navigation panel
3. Toggle on "Enable AI App Features"
4. Add an overview description (e.g., "Insight Mesh Assistant helps you interact with your data using RAG and run agent processes")
5. Configure prompts:
   - You can use fixed prompts as defined in our code, or
   - Select dynamic prompts if you prefer the app to generate them based on context
6. Click "Save Changes"

## Step 2: Enable Socket Mode (for development)

1. Navigate to "Socket Mode" in the left navigation panel
2. Toggle on "Enable Socket Mode"
3. Create an app-level token if prompted:
   - Name your token (e.g., "Insight Mesh Socket Token")
   - Ensure the `connections:write` scope is added
   - Click "Generate"
   - Save the token (starts with `xapp-`) for use in environment variables

## Step 3: Configure Event Subscriptions

1. Navigate to "Event Subscriptions" in the left navigation panel
2. Toggle on "Enable Events"
3. Under "Subscribe to bot events" add the following:
   - `assistant_thread_started`
   - `assistant_thread_context_changed`
   - `message.im`
   - Keep `app_mention` and `message` for backward compatibility
4. Click "Save Changes"

## Step 4: Update OAuth & Permissions

1. Navigate to "OAuth & Permissions" in the left navigation panel
2. Under "Scopes" > "Bot Token Scopes", add the following:
   - `assistant:write` (should be added automatically)
   - `im:history` (to read messages in direct messages)
   - `chat:write` (to send messages)
   - Keep any existing scopes
3. Click "Save Changes"

## Step 5: Reinstall App

1. Navigate to "Install App" in the left navigation panel
2. Click "Reinstall to Workspace" (required after adding new scopes)
3. Review permissions and click "Allow"
4. Note the new Bot User OAuth Token (starts with `xoxb-`) for use in environment variables

## Step 6: Set Environment Variables

Add the following environment variables to your deployment:

```bash
export SLACK_BOT_TOKEN="xoxb-your-bot-token"
export SLACK_APP_TOKEN="xapp-your-app-token"
export LLM_API_URL="http://your-llm-api-url"
export LLM_API_KEY="your-llm-api-key"
export LLM_MODEL="gpt-4" # or other model supported by your LLM API
```

## Step 7: Configure Agent Processes

The bot now supports running agent processes in response to user requests. These processes are defined in the `AGENT_PROCESSES` dictionary in `app_ai.py`.

By default, the following agent processes are available:

1. **Data Indexing Job** - Indexes documents into the RAG system
2. **Slack Import Job** - Imports data from Slack channels

To add or modify agent processes:

1. Edit the `AGENT_PROCESSES` dictionary in `app_ai.py`
2. Make sure commands have the correct paths to their scripts
3. Add corresponding entries to `DEFAULT_PROMPTS` to make them available as prompts
4. Ensure the scripts are available and executable in the expected locations

## Step 8: Run the Bot

Start the bot using:

```bash
python app_ai.py
```

Or using Docker:

```bash
docker build -t insight-mesh-slack-bot .
docker run -d --env-file .env --name insight-mesh-bot insight-mesh-slack-bot
```

## Verifying Setup

1. In Slack, you should see your AI App in the sidebar (may need to search in Apps)
2. Click on the app to open the AI split view
3. Try one of the suggested prompts or ask a question
4. You should see the status indicator while it's thinking and then receive a response
5. Try starting an agent process by using one of the agent prompts (e.g., "Start a data indexing job")
6. The bot should respond with a confirmation that the process has started and provide status details 