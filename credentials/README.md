# Integration Credentials Setup

This directory contains setup instructions and credential files for various integrations.

## Google Drive API Integration

### Required Files
- `credentials.json`: Google Drive API credentials file

### Enable the Google Drive API
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Select your project (or create a new one).
3. Navigate to "APIs & Services" > "Library".
4. Search for "Google Drive API".
5. Click on it and press "Enable".

### Create Service Account Credentials
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project or select an existing one.
3. Navigate to "APIs & Services" > "Credentials".
4. Click "Create Credentials" > "Service Account".
5. Provide a name for the service account and click "Create".
6. Assign the role "Project" > "Viewer" to the service account.
7. Click "Done".
8. Find the service account in the list and click on it.
9. Go to the "Keys" tab and click "Add Key" > "Create new key".
10. Choose "JSON" as the key type and click "Create".
11. The JSON file will be downloaded to your computer.
12. Rename the downloaded file to `credentials.json` and place it in this directory.

### Share Google Drive Folders
1. Get the service account email from the credentials JSON file (look for `client_email`).
2. Share your Google Drive folders with this email address, giving it "Viewer" access.
3. Note the folder IDs (from the URL of your Google Drive folders) and add them to your configuration.

## Slack Integration

### Required Files
- `.env` file with Slack configuration

### Create a Slack App
1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App"
3. Choose "From scratch"
4. Give your app a name and select your workspace
5. Click "Create App"

### Set Up Bot Permissions
1. In the left sidebar, click "OAuth & Permissions"
2. Under "Scopes", add the following bot token scopes:
   - `chat:write` (to send messages)
   - `channels:read` (to get channel information)
   - `channels:join` (to join channels)
   - `users:read` (to read user profiles)
   - `users:read.email` (to read user email addresses)
3. Scroll up and click "Install to Workspace"
4. Copy the "Bot User OAuth Token" (starts with `xoxb-`)

### Environment Variables
Add the following to your `.env` file:

```
# Google Drive Configuration
GOOGLE_DRIVE_FOLDER_IDS=your_folder_ids_here

# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_CHANNEL=#your-channel-name

# Database Configuration
POSTGRES_CONN_STRING=postgresql://username:password@localhost:5432/database_name
```

### Database Schema
The `slack_users` table in PostgreSQL will have the following structure:
- `slack_id` (String, Primary Key): The unique Slack user ID
- `slack_username` (String): The user's Slack username
- `email` (String): The user's email address
- `real_name` (String): The user's real name
- `display_name` (String): The user's display name
- `raw_data` (JSONB): Additional user data in JSON format

## Security Notes

### General Security
- Never commit credentials or tokens to version control
- Use environment variables or secure secrets managers
- Grant only the minimum required permissions
- Regularly rotate credentials and tokens

### Google Drive Security
- Keep your service account credentials secure
- Regularly audit folder sharing permissions
- Monitor API usage for unusual activity

### Slack Security
- Keep your bot token secure
- Monitor bot activity and permissions
- Regularly review and update scopes

### Database Security
- Ensure your PostgreSQL connection string is properly secured
- Consider implementing row-level security
- Regularly backup your database
- Monitor database access and queries 