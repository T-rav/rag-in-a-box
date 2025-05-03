#!/bin/bash

echo "Verifying Elasticsearch setup..."
echo "==============================="

# Check if Elasticsearch is running
if curl -s http://localhost:9200 > /dev/null; then
    echo "✓ Elasticsearch is running"
    
    # Check google_drive_files index
    if curl -s http://localhost:9200/google_drive_files > /dev/null; then
        echo "✓ google_drive_files index exists"
        
        # Check mappings
        echo "Index mappings:"
        curl -s http://localhost:9200/google_drive_files/_mapping | jq .
    else
        echo "✗ google_drive_files index does not exist"
    fi
else
    echo "✗ Elasticsearch is not running"
fi

echo -e "\nVerifying Neo4j setup..."
echo "========================="

# Check if Neo4j is running
if curl -s http://localhost:7474 > /dev/null; then
    echo "✓ Neo4j is running"
    
    # Check constraints
    echo "Constraints:"
    curl -s -u neo4j:password http://localhost:7474/db/neo4j/tx/commit -H "Content-Type: application/json" -d '{"statements":[{"statement":"SHOW CONSTRAINTS"}]}' | jq .
    
    # Check indexes
    echo -e "\nIndexes:"
    curl -s -u neo4j:password http://localhost:7474/db/neo4j/tx/commit -H "Content-Type: application/json" -d '{"statements":[{"statement":"SHOW INDEXES"}]}' | jq .
    
    # Check metadata
    echo -e "\nMetadata:"
    curl -s -u neo4j:password http://localhost:7474/db/neo4j/tx/commit -H "Content-Type: application/json" -d '{"statements":[{"statement":"MATCH (m:Metadata) RETURN m"}]}' | jq .
else
    echo "✗ Neo4j is not running"
fi 