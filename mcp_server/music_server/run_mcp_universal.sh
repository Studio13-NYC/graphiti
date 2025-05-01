#!/bin/bash

# Navigate to the script's directory
cd "$(dirname "$0")" || exit

# Define the main server script within this directory
SERVER_SCRIPT="./server.py" # Use the server.py in the current music_server directory

# Define parameters
MODEL="gpt-4o-mini"
EMBEDDER_MODEL="text-embedding-3-small"
TRANSPORT="sse"
PORT="8000"
GROUP_ID="s13-music" # Example group ID
USE_CUSTOM_ENTITIES="--use-custom-entities" # Flag for custom entities
# USE_STREAMLINED="--use-streamlined" # Flag for streamlined tools, enable if needed

# Add the root 'graphiti' directory to PYTHONPATH if necessary
# Assumes the script is run from within the 'music_server' directory
export PYTHONPATH="../../:$PYTHONPATH" 
echo "PYTHONPATH: $PYTHONPATH"

# Check if the server script exists
if [ ! -f "$SERVER_SCRIPT" ]; then
  echo "Error: Server script not found at $SERVER_SCRIPT"
  exit 1
fi

echo "Starting Graphiti Music MCP Server with $(basename "$SERVER_SCRIPT")..."

# Construct the command - include flags conditionally
COMMAND="uv run $SERVER_SCRIPT \
  --model $MODEL \
  --embedder-model $EMBEDDER_MODEL \
  --transport $TRANSPORT \
  --port $PORT \
  --group-id $GROUP_ID \
  $USE_CUSTOM_ENTITIES"
  # Add $USE_STREAMLINED here if you want to enable it by default

echo "Running command: $COMMAND"

# Execute the command
eval $COMMAND