# Dagster Project

This project contains data import and processing pipelines using Dagster.

## Slack Import

The Slack import pipeline allows importing data from a Slack workspace, including user information, channel details, and channel content.

### Features

- User information import (profiles, emails, etc.)
- Channel information import (names, descriptions, etc.)
- Channel content import (messages, pins, bookmarks, etc.)
- Neo4j and Elasticsearch integration for data storage
- Separate jobs for users and channels/content

### Running the Slack Import

The Slack import is separated into two jobs:

1. `slack_users_job`: Imports only user information
2. `slack_channels_job`: Imports channel information and content

#### Using Dagster UI

1. Start the Dagster UI:
   ```bash
   dagster dev
   ```

2. Navigate to http://localhost:3000
3. Select either the `slack_users_job` or `slack_channels_job` to run

#### Using Dagster CLI

You can run jobs directly from the command line:

```bash
# Import only user information
dagster job execute -f slack_assets.py -a slack_users_job

# Import channel information and content
dagster job execute -f slack_assets.py -a slack_channels_job
```

#### Using schedules

The following schedules are configured:

- `slack_users_schedule`: Runs the user import once per day
- `slack_channels_schedule`: Runs the channel and content import every 6 hours

### Configuration

Slack import requires the following environment variables:

- `SLACK_BOT_TOKEN`: OAuth token for the Slack API
- `NEO4J_URI`: URI for Neo4j connection (e.g., `bolt://localhost:7687`)
- `NEO4J_USER`: Neo4j username
- `NEO4J_PASSWORD`: Neo4j password
- `ELASTICSEARCH_HOST`: Elasticsearch host
- `ELASTICSEARCH_PORT`: Elasticsearch port

You can configure import behavior through the `SlackConfig` class parameters:
- `max_messages_per_channel`: Maximum number of messages to import per channel
- `include_threads`: Whether to include thread messages
- `include_reactions`: Whether to include reactions
- `include_files`: Whether to include files
- `include_canvases`: Whether to include canvases
- `include_links`: Whether to include link information

## Other Data Sources

[Documentation for other data sources would go here]

## Overview

The pipelines handle:
1. Authentication with Google Drive via service account credentials
2. Document discovery and permissions mapping
3. Document indexing into Haystack
4. Scheduled refreshes to keep the index up-to-date

## Setup

1. Install dependencies:
```bash
pip install dagster dagster-webserver dagster-postgres google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

2. Configure Google Drive credentials in `.env` file or environment variables

3. Run the Dagster UI:
```bash
dagster dev
```

## Pipelines

- `google_drive_indexer`: Fetches documents from Google Drive and indexes them in Haystack
- `refresh_schedule`: Refreshes the index on a regular schedule

## Integration with Haystack and LiteLLM

The Dagster pipelines connect to Haystack for document indexing, and the indexed documents are then used by LiteLLM for RAG operations. 