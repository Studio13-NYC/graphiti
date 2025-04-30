#!/usr/bin/env bash
cd "$(dirname "$0")"
echo "[INFO] Starting Graphiti MCP server..."
uv run graphiti_mcp_server.py --model gpt-4o-mini --transport sse --group-id s13 --port 5081 , --use-custom-entities