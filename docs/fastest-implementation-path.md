# Fastest Implementation Path: Graphiti MCP Server

This guide outlines the quickest path to rebuild the core functionality of the Graphiti MCP server.

**Estimated Time:** 1-2 days (assuming familiarity with Python, Asyncio, Docker, Neo4j)

## Stage 1: Core Setup & Dependencies (Est: 2-4 hours)

1.  **Prerequisites:**
    *   Install Python 3.11+.
    *   Install `uv`: `curl -LsSf https://astral.sh/uv/install.sh | sh`
    *   Install Docker & Docker Compose.
    *   Obtain an OpenAI API Key.

2.  **Project Structure:**
    ```bash
    mkdir graphiti-mcp-rebuild
    cd graphiti-mcp-rebuild
    mkdir mcp_server
    cd mcp_server
    ```

3.  **Dependencies (`mcp_server/pyproject.toml`):**
    ```toml
    [project]
    name = "mcp-server-rebuild"
    version = "0.1.0"
    description = "Graphiti MCP Server Rebuild"
    requires-python = ">=3.11"
    dependencies = [
        "mcp>=1.5.0",
        "openai>=1.68.2",
        "graphiti-core>=0.8.2",
        "pydantic", # Explicitly add, though likely pulled in by others
        "python-dotenv",
        "uvicorn[standard]", # Needed for FastMCP/SSE
        # Defer azure-identity until needed
    ]
    ```
    *Run `uv sync` in the `mcp_server` directory.* (Requires network access)

4.  **Neo4j Setup (Docker):** Create `mcp_server/docker-compose.yml`:
    ```yaml
    services:
      neo4j:
        image: neo4j:5.26.0
        ports:
          - "7474:7474"
          - "7687:7687"
        environment:
          - NEO4J_AUTH=neo4j/password # Use a secure password
          # Keep memory settings low initially
          - NEO4J_server_memory_heap_max__size=512m
          - NEO4J_server_memory_pagecache_size=256m
        volumes:
          - neo4j_data:/data
        healthcheck:
          test: ["CMD", "wget", "-O", "/dev/null", "http://localhost:7474"]
          interval: 10s
          timeout: 5s
          retries: 5
          start_period: 30s

    volumes:
      neo4j_data:
    ```
    *Run `docker compose up -d neo4j`.* Wait for it to become healthy.

5.  **Configuration (`mcp_server/.env`):**
    ```dotenv
    NEO4J_URI=bolt://localhost:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=password # Match docker-compose
    OPENAI_API_KEY=sk-YOUR_API_KEY_HERE
    MODEL_NAME=gpt-4o-mini # Or other suitable model
    EMBEDDER_MODEL_NAME=text-embedding-3-small
    ```

## Stage 2: Basic Server & Graphiti Client (Est: 3-5 hours)

1.  **Create `mcp_server/server.py`:**
    *   Import necessary libraries (`asyncio`, `logging`, `os`, `argparse`, `dotenv`, `pydantic`, `mcp`, `graphiti_core`, `openai`).
    *   Set up basic logging.
    *   Load environment variables using `dotenv.load_dotenv()`.
    *   Define Pydantic config models (simplified `Neo4jConfig`, `GraphitiLLMConfig`, `GraphitiEmbedderConfig`, `GraphitiConfig`, `MCPConfig` - initially focus only on needed fields like Neo4j creds, OpenAI key/models, group_id, transport).
    *   Implement `from_env` and `from_cli_and_env` methods for `GraphitiConfig` (handle basic CLI args: `--transport`, `--group-id`, `--model`).
    *   Create `initialize_graphiti` async function:
        *   Takes the `GraphitiConfig`.
        *   Creates basic `OpenAIEmbedder` and `OpenAIClient` instances (defer Azure/CrossEncoder logic).
        *   Initializes `Graphiti` client with Neo4j creds, embedder, and LLM client.
        *   Calls `graphiti_client.build_indices_and_constraints()`.
        *   Handles potential initialization errors.
    *   Create `main` async function:
        *   Parse CLI arguments.
        *   Create `GraphitiConfig` and `MCPConfig`.
        *   Call `initialize_graphiti`.
        *   Instantiate `FastMCP`.
        *   Implement basic `asyncio.run(mcp.run_stdio_async())` or `asyncio.run(mcp.run_sse_async())` based on config.
    *   Add `if __name__ == '__main__': asyncio.run(main())`.

2.  **Initial Test:** Run `uv run server.py --transport stdio`. It should connect to Neo4j and start the MCP server without errors.

## Stage 3: Core MCP Tools (Est: 4-6 hours)

1.  **Implement `add_episode` Tool:**
    *   Define the `@mcp.tool()` async function `add_episode` with parameters (`name`, `episode_body`, `group_id`, `source`, `source_description`, `uuid`).
    *   **Shortcut:** Initially, implement *synchronous* processing directly within the tool function (defer async queue for speed).
    *   Get the global `graphiti_client`.
    *   Determine `effective_group_id` (use provided or default from config).
    *   Map `source` string to `EpisodeType` enum.
    *   Call `graphiti_client.add_episode(...)` with the necessary parameters (initially, pass `entity_types={}`).
    *   Return success/error dictionary.

2.  **Implement `search_nodes` Tool:**
    *   Define `@mcp.tool()` async function `search_nodes` (`query`, `group_ids`, `max_nodes`, `center_node_uuid`, `entity`).
    *   Get `graphiti_client`.
    *   Determine `effective_group_ids`.
    *   **Shortcut:** Use a simple default search config (`NODE_HYBRID_SEARCH_RRF`) without complex logic based on `center_node_uuid` initially.
    *   Call `graphiti_client._search(...)`.
    *   Format results into the required `NodeResult` TypedDict structure (simplify formatting initially).
    *   Return `NodeSearchResponse` or `ErrorResponse`.

3.  **Implement `search_facts` Tool:**
    *   Define `@mcp.tool()` async function `search_facts` (`query`, `group_ids`, `max_facts`, `center_node_uuid`).
    *   Get `graphiti_client`.
    *   Determine `effective_group_ids`.
    *   Call `graphiti_client.search(...)`.
    *   Format results using `edge.model_dump(mode='json', exclude={'fact_embedding'})`.
    *   Return `FactSearchResponse` or `ErrorResponse`.

4.  **Test Core Tools:** Use an MCP client (or manually craft MCP JSON messages via stdio) to test adding episodes and searching.

## Stage 4: Refinements & Remaining Tools (Est: 3-5 hours)

1.  **Implement Async Queue for `add_episode`:**
    *   Introduce the `episode_queues` dict and `queue_workers` dict.
    *   Create the `process_episode_queue` async worker function.
    *   Modify `add_episode` to put an async processing function onto the correct queue and start the worker if needed, returning immediately.

2.  **Implement Other Tools:** Add the remaining tools (`delete_entity_edge`, `delete_episode`, `get_entity_edge`, `get_episodes`, `clear_graph`, `get_status`) by wrapping the corresponding `graphiti-core` methods, similar to `search_facts` or `search_nodes`.

3.  **Add SSE Support:** Ensure `uvicorn` is installed (`uv pip install uvicorn[standard]`). Add logic in `main` to call `mcp.run_sse_async()` when `transport == 'sse'`. Configure host/port as needed (e.g., `mcp.settings.port = args.port`).

4.  **Dockerize:** Create `mcp_server/Dockerfile` (copy from original, ensure it uses `server.py`). Update `docker-compose.yml` to build and run the `graphiti-mcp` service, linking it to Neo4j and passing environment variables.

5.  **Final Testing:** Test both stdio and SSE transports, all tools, and Docker deployment.

This path prioritizes getting a functional server with core capabilities quickly, deferring complexities like Azure support, custom entity extraction, sophisticated search configurations, and potentially the cross-encoder until the base is solid. 