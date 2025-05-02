#!/bin/bash

# Wait for Elasticsearch to be ready
until curl -s http://localhost:9200 > /dev/null; do
    echo 'Waiting for Elasticsearch to be ready...'
    sleep 5
done

# Create google_drive_files index with proper mappings
curl -X PUT "http://localhost:9200/google_drive_files" -H "Content-Type: application/json" -d'
{
  "settings": {
    "analysis": {
      "analyzer": {
        "custom_analyzer": {
          "type": "custom",
          "tokenizer": "standard",
          "filter": ["lowercase", "asciifolding"]
        }
      }
    }
  },
  "mappings": {
    "properties": {
      "id": { "type": "keyword" },
      "name": { 
        "type": "text",
        "analyzer": "custom_analyzer",
        "fields": {
          "keyword": { "type": "keyword" }
        }
      },
      "mimeType": { "type": "keyword" },
      "createdTime": { "type": "date" },
      "modifiedTime": { "type": "date" },
      "webViewLink": { "type": "keyword" },
      "content": { 
        "type": "text",
        "analyzer": "custom_analyzer"
      },
      "owners": {
        "type": "nested",
        "properties": {
          "emailAddress": { "type": "keyword" },
          "displayName": { 
            "type": "text",
            "analyzer": "custom_analyzer"
          }
        }
      },
      "parents": { "type": "keyword" }
    }
  }
}'

# Create a template for future indices
curl -X PUT "http://localhost:9200/_index_template/google_drive_template" -H "Content-Type: application/json" -d'
{
  "index_patterns": ["google_drive_*"],
  "template": {
    "settings": {
      "analysis": {
        "analyzer": {
          "custom_analyzer": {
            "type": "custom",
            "tokenizer": "standard",
            "filter": ["lowercase", "asciifolding"]
          }
        }
      }
    },
    "mappings": {
      "properties": {
        "id": { "type": "keyword" },
        "name": { 
          "type": "text",
          "analyzer": "custom_analyzer",
          "fields": {
            "keyword": { "type": "keyword" }
          }
        },
        "mimeType": { "type": "keyword" },
        "createdTime": { "type": "date" },
        "modifiedTime": { "type": "date" },
        "content": { 
          "type": "text",
          "analyzer": "custom_analyzer"
        }
      }
    }
  }
}'

echo "Elasticsearch initialization complete!" 