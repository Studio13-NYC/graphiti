# Integrating the Graphiti Music MCP Server

This document outlines the structure and usage of the specialized Music MCP Server variant located in `mcp_server/music_server/`.

## Overview

The Music MCP Server extends the base Graphiti MCP server functionality by:

1.  **Defining Music-Specific Entities:** It includes Pydantic models for common music concepts like `Artist`, `Album`, `Track`, `Label`, `Performance`, etc. (defined in `music_server/models/music.py`).
2.  **Enabling Custom Entity Extraction:** When run with the `--use-custom-entities` flag, it instructs `graphiti-core` to attempt extraction of these specific music entities from ingested data (via `add_episode`).
3.  **Providing Specialized Tools:** It includes an `add_track` tool specifically designed for adding track information and potentially linking it to artists and albums (though relationship linking might require further refinement).
4.  **Maintaining Base Functionality:** It retains all standard Graphiti MCP tools (`add_episode`, `search_nodes`, `search_facts`, etc.) for general data handling.

## Code Structure

The `music_server/` directory follows a modular structure:

*   **`server.py`:** The main application entry point. Handles:
    *   Command-line argument parsing.
    *   Loading configuration (`.env`, CLI args).
    *   Initializing the `Graphiti` client.
    *   Setting up the `FastMCP` server instance.
    *   Registering all available MCP tools.
    *   Running the server loop (SSE or stdio).
*   **`config.py`:** Defines Pydantic models for server configuration (`GraphitiConfig`, `MCPConfig`, `Neo4jConfig`, `GraphitiLLMConfig`, `GraphitiEmbedderConfig`), including logic for loading from environment variables and CLI arguments.
*   **`tools.py`:** Defines all MCP tools available through this server:
    *   Standard Graphiti tools (`add_episode`, `search_nodes`, `search_facts`, `delete_*`, `get_*`, `clear_graph`, `get_status`).
    *   The custom `add_track` tool.
    *   Contains the `MUSIC_ENTITY_TYPES` dictionary mapping music model names (e.g., "Album") to their Pydantic classes. This dictionary is used by `add_episode` when `--use-custom-entities` is enabled.
    *   Includes helper functions (e.g., `format_fact_result`) and the async episode processing queue logic.
*   **`models/`:** Directory containing Pydantic models.
    *   **`music.py`:** Defines all music-specific entity models (`Artist`, `Album`, `Track`, etc.) as well as the base `Requirement`, `Preference`, `Procedure` models (included for completeness, but could be removed if only music entities are desired).
    *   **`__init__.py`:** Makes `models` a package.
*   **`run_music_server_sse.sh`:** Example bash script to run the server using `uv` with SSE transport and custom entity extraction enabled.

## Model Usage and Neo4j Labels

A key requirement is that the Pydantic model names directly translate to the labels used for entities in Neo4j when extracted.

*   **How it works:** The `MUSIC_ENTITY_TYPES` dictionary in `tools.py` maps the *string name* of the entity (e.g., `'Album'`) to the corresponding Pydantic class (e.g., `Album`).
*   **Graphiti Integration:** When `graphiti-core` performs entity extraction (triggered by `add_episode` with `--use-custom-entities` enabled and this `MUSIC_ENTITY_TYPES` dictionary provided), it uses the *keys* of this dictionary (the strings like `'Album'`, `'Artist'`) as the **labels** for the corresponding nodes created in Neo4j.
*   **Example:** If `graphiti-core` identifies text corresponding to the `Album` model, it will create a node in Neo4j with the label `:Album` and properties derived from the `Album` Pydantic model fields.

## Running the Music Server

1.  **Prerequisites:** Ensure Python, `uv`, Docker (for Neo4j), and a running Neo4j instance are available.
2.  **Environment:** Set necessary environment variables (e.g., `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `OPENAI_API_KEY`) directly or in a `.env` file within the `music_server` directory.
3.  **Dependencies:** Navigate to the *parent* `mcp_server` directory and run `uv sync` to install dependencies listed in `mcp_server/pyproject.toml`.
4.  **Execution:**
    *   Navigate to the `mcp_server/music_server/` directory.
    *   Use the provided script: `bash run_music_server_sse.sh`
    *   Or run directly using `uv`:
        ```bash
        # Example: SSE transport, custom entities enabled
        uv run server.py --transport sse --use-custom-entities --group-id my_music_graph

        # Example: Stdio transport, default entities only
        uv run server.py --transport stdio 
        ```

## Key Considerations

*   **`--use-custom-entities` Flag:** This flag *must* be passed when running `server.py` if you want the server to attempt extraction of the specific music entities defined in `models/music.py`. Without it, only generic entity extraction (if any) will occur via `add_episode`.
*   **`add_track` vs `add_episode`:**
    *   `add_track` is a specialized tool for directly adding track data. It attempts to create a `Track` node via `add_episode_node` using `source=json`.
    *   `add_episode` (with `source=json` or `source=text`/`message` and `--use-custom-entities`) is the general mechanism where `graphiti-core` analyzes the input and extracts any matching entities from `MUSIC_ENTITY_TYPES`.
*   **Dependencies:** This server relies on the packages defined in the main `mcp_server/pyproject.toml`.
*   **Configuration:** Server behavior (models, database, transport, etc.) is controlled via environment variables and the command-line arguments defined in `server.py`. 