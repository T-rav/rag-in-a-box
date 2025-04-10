#!/bin/bash

# Script to set up Google OAuth credentials for RAG in a Box

echo "RAG in a Box - Google Authentication Setup"
echo "=========================================="
echo ""
echo "This script will help you set up Google OAuth credentials for your RAG in a Box deployment."
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
  echo "Creating .env file..."
  touch .env
fi

# Prompt for Google OAuth credentials
echo "Please visit https://console.cloud.google.com/apis/credentials to create OAuth credentials."
echo "Make sure to set the authorized redirect URI to: http://localhost/auth/oauth2/google/authorization-code-callback"
echo ""
read -p "Enter your Google Client ID: " CLIENT_ID
read -p "Enter your Google Client Secret: " CLIENT_SECRET
read -p "Enter the allowed email domain (default: gmail.com): " EMAIL_DOMAIN
EMAIL_DOMAIN=${EMAIL_DOMAIN:-gmail.com}
read -p "Enter the domain for your deployment (default: localhost): " DOMAIN
DOMAIN=${DOMAIN:-localhost}

# Update .env file
echo "Updating .env file with Google OAuth credentials..."

# Check if OPENAI_API_KEY already exists in .env
if grep -q "OPENAI_API_KEY" .env; then
  echo "OPENAI_API_KEY already exists in .env file."
else
  read -p "Enter your OpenAI API Key: " OPENAI_API_KEY
  echo "OPENAI_API_KEY=$OPENAI_API_KEY" >> .env
fi

# Add Google OAuth credentials to .env
grep -v "GOOGLE_CLIENT_ID\|GOOGLE_CLIENT_SECRET\|DOMAIN\|ALLOWED_EMAIL_DOMAIN" .env > .env.tmp
echo "GOOGLE_CLIENT_ID=$CLIENT_ID" >> .env.tmp
echo "GOOGLE_CLIENT_SECRET=$CLIENT_SECRET" >> .env.tmp
echo "DOMAIN=$DOMAIN" >> .env.tmp
echo "ALLOWED_EMAIL_DOMAIN=$EMAIL_DOMAIN" >> .env.tmp
mv .env.tmp .env

echo ""
echo "Setup complete! Your Google OAuth credentials have been added to the .env file."
echo "You can now start your RAG in a Box deployment with: docker-compose up -d"
echo ""
echo "Your RAG in a Box will be available at: http://localhost"
echo "Only users with email addresses ending in @$EMAIL_DOMAIN will be allowed to access the application."
