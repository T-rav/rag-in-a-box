FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the Dagster code
COPY . .

# Expose the port that dagster webserver will run on
EXPOSE 3000

# Start the dagster webserver
CMD ["dagster", "dev", "-h", "0.0.0.0", "-p", "3000", "-f", "google_drive_assets.py"] 