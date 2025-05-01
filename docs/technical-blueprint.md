# Technical Blueprint: Graphiti MCP Server (Fast Rebuild)

This blueprint outlines the essential components and minimal features for the fastest rebuild.

## Essential Components (Implement First)

1.  **Configuration Module (`config.py` or within `server.py`):**
    *   Pydantic models: `Neo4jConfig`, `GraphitiLLMConfig`, `GraphitiEmbedderConfig`, `GraphitiConfig`, `MCPConfig`.
    *   Focus on essential fields: Neo4j URI/User/Pass, OpenAI Key/Models, Group ID, Transport.
    *   Load from `.env` and basic CLI args (`--transport`, `--group-id`).

2.  **Graphiti Client Initialization (`initialize_graphiti` in `server.py`):**
    *   Takes `GraphitiConfig`.
    *   Creates `OpenAIEmbedder` and `OpenAIClient` (using config).
    *   Initializes `graphiti_core.Graphiti`.
    *   Calls `graphiti_client.build_indices_and_constraints()`.
    *   Basic error handling/logging.

3.  **MCP Server Setup (`main` in `server.py`):**
    *   Argument parsing (`argparse`).
    *   Load config.
    *   Call `initialize_graphiti`.
    *   Instantiate `mcp.server.fastmcp.FastMCP`.
    *   Register core tools (see below).
    *   Run loop (`mcp.run_stdio_async()` initially).

4.  **Core MCP Tools (`server.py`):**
    *   `add_episode`: Wrapper around `graphiti_client.add_episode`. Start synchronous, add async queue later.
    *   `search_nodes`: Wrapper around `graphiti_client._search` (using simple `NODE_HYBRID_SEARCH_RRF` config).
    *   `search_facts`: Wrapper around `graphiti_client.search`.

## Simplified Data Models/Schemas

*   **Focus on Core Graph Structure:** Rely entirely on the implicit schemas created by `graphiti-core` when adding episodes and extracting entities/facts.
*   **Defer Custom Entities:** Do *not* implement the `Requirement`, `Preference`, `Procedure` Pydantic models or the `--use-custom-entities` flag logic initially. Pass `entity_types={}` to `add_episode`.
*   **Tool Responses:** Use basic Python dictionaries or `TypedDict` for tool responses (`SuccessResponse`, `ErrorResponse`, `NodeResult`, `NodeSearchResponse`, `FactSearchResponse`) as defined in the original code. Pydantic models for responses are not strictly necessary for the MCP protocol itself.

## Core API/Functions to Prioritize

These correspond to the essential MCP tools:

1.  **`add_episode(name, episode_body, group_id, source, ...)`:**
    *   **Minimal Viable:** Accepts text (`source='text'`), connects to Graphiti, calls `graphiti_client.add_episode`. Basic error handling. Returns success/failure message.
    *   **Next Step:** Implement async queue processing.
    *   **Later:** Add support for `source='json'` and `source='message'`. Add custom entity logic if needed.

2.  **`search_nodes(query, group_ids, max_nodes, ...)`:**
    *   **Minimal Viable:** Accepts query, calls `graphiti_client._search` with default config, formats basic node info (UUID, name, summary, group_id), returns list.
    *   **Later:** Implement filtering (`entity`), `center_node_uuid` logic, refined formatting.

3.  **`search_facts(query, group_ids, max_facts, ...)`:**
    *   **Minimal Viable:** Accepts query, calls `graphiti_client.search`, formats facts using `model_dump`, returns list.
    *   **Later:** Implement `center_node_uuid`.

4.  **`initialize_graphiti()`:** Crucial setup function.
5.  **`main()` / Server Run Loop:** Essential for running the server.

## Minimal Viable Features per Milestone

1.  **Milestone 1 (Core Setup):**
    *   Project structure created.
    *   Dependencies installed (`uv sync`).
    *   Neo4j running (Docker).
    *   Basic configuration loading from `.env`.
    *   `server.py` exists, can run via `uv run`, connects to Neo4j, initializes `Graphiti` client, starts basic MCP loop (stdio) without errors.

2.  **Milestone 2 (Basic I/O):**
    *   `add_episode` tool implemented (synchronously).
    *   `search_nodes` tool implemented (basic version).
    *   `search_facts` tool implemented (basic version).
    *   Can add data and retrieve nodes/facts using an MCP client via stdio.

3.  **Milestone 3 (Refinement & Remaining Tools):**
    *   `add_episode` uses async queue.
    *   Other tools (`delete_*`, `get_*`, `clear_graph`, `get_status`) implemented.
    *   SSE transport (`mcp.run_sse_async()`) is working.
    *   Basic Docker deployment (`Dockerfile`, `docker-compose.yml` for the app service) functional.

## Skeleton Code Examples

**Basic `server.py` Structure:**

```python
import asyncio
import logging
import os
import argparse
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from graphiti_core import Graphiti
from graphiti_core.embedder.openai import OpenAIEmbedder
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.nodes import EpisodeType
# Import Pydantic models for config
# Import TypedDicts for responses

load_dotenv()
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# --- Pydantic Config Classes --- 
# (Neo4jConfig, GraphitiLLMConfig, GraphitiEmbedderConfig, GraphitiConfig, MCPConfig)

graphiti_client: Graphiti | None = None
config: GraphitiConfig | None = None

mcp = FastMCP('graphiti-rebuild', instructions='Basic Graphiti MCP Server')

async def initialize_graphiti(cfg: GraphitiConfig):
    global graphiti_client
    try:
        # Simplified client creation
        llm_client = OpenAIClient(config=LLMConfig(api_key=cfg.llm.api_key, model=cfg.llm.model))
        embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(api_key=cfg.embedder.api_key, model=cfg.embedder.model))

        graphiti_client = Graphiti(
            uri=cfg.neo4j.uri,
            user=cfg.neo4j.user,
            password=cfg.neo4j.password,
            llm_client=llm_client,
            embedder=embedder,
        )
        await graphiti_client.build_indices_and_constraints()
        logger.info('Graphiti initialized')
    except Exception as e:
        logger.error(f'Graphiti init failed: {e}')
        raise

# --- MCP Tool Definitions --- 
# (@mcp.tool async def add_episode(...): ...)
# (@mcp.tool async def search_nodes(...): ...)
# (@mcp.tool async def search_facts(...): ...)

async def main():
    global config
    parser = argparse.ArgumentParser()
    # Add args: --transport, --group-id, --model, --port
    args = parser.parse_args()

    config = GraphitiConfig.from_cli_and_env(args)
    mcp_config = MCPConfig.from_cli(args)

    await initialize_graphiti(config)

    logger.info(f'Starting MCP server via {mcp_config.transport}')
    if mcp_config.transport == 'stdio':
        await mcp.run_stdio_async()
    elif mcp_config.transport == 'sse':
        mcp.settings.port = args.port # Assuming port arg exists
        await mcp.run_sse_async()

if __name__ == '__main__':
    asyncio.run(main())
```

**Simplified `add_episode` (Sync Initial Version):**

```python
@mcp.tool()
async def add_episode(name: str, episode_body: str, group_id: str | None = None, ...) -> dict:
    if not graphiti_client or not config:
        return {'error': 'Server not initialized'}
    try:
        effective_group_id = group_id or config.group_id
        # Map source string to EpisodeType enum
        source_type = EpisodeType.text # Default

        await graphiti_client.add_episode(
            name=name,
            episode_body=episode_body,
            source=source_type,
            group_id=str(effective_group_id),
            entity_types={} # Defer custom entities
            # ... other params
        )
        return {'message': 'Episode added'}
    except Exception as e:
        logger.error(f'Add episode failed: {e}')
        return {'error': str(e)}
``` 