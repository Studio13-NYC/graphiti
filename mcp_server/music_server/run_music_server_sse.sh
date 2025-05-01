#!/bin/bash
# Example script to run the Music Graphiti MCP server with SSE transport

# Load environment variables from .env file if it exists
if [ -f .env ]; then
  export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

# Activate virtual environment if necessary
# source ../.venv/bin/activate 

# Check if OpenAI key is set
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY environment variable is not set."
    echo "Please set it before running the server. For example:"
    echo "export OPENAI_API_KEY='your-api-key-here'"
    exit 1
fi

# Set Neo4j credentials (defaults if not set)
NEO4J_URI=${NEO4J_URI:-"bolt://localhost:7687"}
NEO4J_USER=${NEO4J_USER:-"neo4j"}
NEO4J_PASSWORD=${NEO4J_PASSWORD:-"password"}

# Set OpenAI models
OPENAI_MODEL=${OPENAI_MODEL:-"gpt-4o"}
OPENAI_EMBEDDING_MODEL=${OPENAI_EMBEDDING_MODEL:-"text-embedding-3-small"}

# Run server with SSE transport on port 8000 (default)
# Using the new streamlined tools by default
python -m music_server.server \
    --transport sse \
    --model $OPENAI_MODEL \
    --embedder-model $OPENAI_EMBEDDING_MODEL \
    --use-streamlined \
    "$@" 