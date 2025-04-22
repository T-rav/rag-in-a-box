# Dagster Integration for Insight Mesh

This directory contains Dagster pipelines for integrating Google Drive with Haystack for the Insight Mesh RAG system.

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