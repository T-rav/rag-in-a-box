# Slack Bot Integration Setup

This guide will help you set up a Slack bot for integration with your Dagster project.

## Creating a Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App"
3. Choose "From scratch"
4. Give your app a name and select your workspace
5. Click "Create App"

## Setting Up Bot Permissions

1. In the left sidebar, click "OAuth & Permissions"
2. Under "Scopes", add the following bot token scopes:
   - `chat:write` (to send messages)
   - `channels:read` (to get channel information)
   - `channels:join` (to join channels)
   - `users:read` (to read user profiles)
   - `users:read.email` (to read user email addresses)
3. Scroll up and click "Install to Workspace"
4. Copy the "Bot User OAuth Token" (starts with `xoxb-`)

## Environment Variables

Add the following environment variables to your `.env` file:

```
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_CHANNEL=#your-channel-name
POSTGRES_CONN_STRING=postgresql://username:password@localhost:5432/database_name
```

## Testing the Integration

1. Make sure your bot is invited to the channel you want to use
2. Run the `slack_test_message` asset to send a test message
3. Run the `slack_channel_info` asset to verify channel access
4. Run the `slack_users` asset to fetch and store user data in PostgreSQL

## Database Schema

The `slack_users` table in PostgreSQL will have the following structure:
- `slack_id` (String, Primary Key): The unique Slack user ID
- `slack_username` (String): The user's Slack username
- `email` (String): The user's email address
- `real_name` (String): The user's real name
- `display_name` (String): The user's display name
- `raw_data` (JSONB): Additional user data in JSON format

## Security Notes

- Keep your bot token secure and never commit it to version control
- The bot token should be stored in environment variables or a secure secrets manager
- Only grant the minimum required permissions to your bot
- Ensure your PostgreSQL connection string is properly secured
- Consider implementing row-level security in PostgreSQL if needed 