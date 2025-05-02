#!/bin/bash

# Create plugins directory if it doesn't exist
mkdir -p plugins

# Download APOC plugin
APOC_VERSION="5.13.0"
curl -L -o plugins/apoc-${APOC_VERSION}-all.jar https://github.com/neo4j-contrib/neo4j-apoc-procedures/releases/download/${APOC_VERSION}/apoc-${APOC_VERSION}-all.jar

echo "APOC plugin downloaded successfully!" 