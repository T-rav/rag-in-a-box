#!/bin/bash

# Navigate to the MCP server directory (if running from elsewhere)
cd "$(dirname "$0")"

# Check if a virtual environment exists or create one
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate the virtual environment
source venv/bin/activate

# Install development dependencies
echo "Installing development dependencies..."
pip install -r requirements-dev.txt

# Run the tests with pytest
echo "Running tests..."
python -m pytest tests/ -v --cov=. --cov-report=term-missing

# Deactivate virtual environment
deactivate

echo "Tests completed!" 