# Project Overview: Graphiti MCP Server

## Summary

This project implements a Model Context Protocol (MCP) server for the Graphiti framework. Graphiti builds and manages temporally-aware knowledge graphs, designed for AI agents needing persistent memory that evolves with user interactions and data updates.

The MCP server acts as a bridge, exposing core Graphiti functionalities (adding/querying data, managing entities/relationships) to MCP-compatible clients (like AI assistants or IDEs) via standard protocols (`stdio` or HTTP SSE). This allows agents to leverage Graphiti's knowledge graph capabilities for context and memory.

## Key Technologies & Frameworks

*   **Programming Language:** Python (>=3.10, specifically 3.11 used in Docker)
*   **Core Logic:** `graphiti-core` (Python library, >=0.8.2) - Handles all knowledge graph operations.
*   **Server Protocol:** `mcp` (Python library, >=1.5.0) - Implements the Model Context Protocol. `FastMCP` is used for the server implementation.
*   **Database:** Neo4j (>=5.26.0) - Required graph database backend.
*   **AI Integration:** `openai` (Python library, >=1.68.2) - For LLM and embedding operations (OpenAI or Azure OpenAI).
*   **Package Management:** `uv` - Used for dependency installation and running the server.
*   **Configuration:** Pydantic - Used for robust configuration management via environment variables and CLI arguments.
*   **Containerization:** Docker & Docker Compose - For reproducible deployment and easy dependency management (especially Neo4j).
*   **Async:** `asyncio` - Used extensively for non-blocking I/O and background task processing.

## Critical Architectural Decisions

*   **MCP Interface:** Exposing Graphiti via MCP provides a standardized way for AI agents/clients to interact with the knowledge graph memory.
*   **`graphiti-core` Reliance:** Building directly on the `graphiti-core` library leverages its specialized graph functionalities instead of reinventing them.
*   **Environment/CLI Configuration:** Using Pydantic for layered configuration (defaults -> env -> CLI) provides flexibility for different deployment scenarios.
*   **Asynchronous Episode Processing:** Implementing a background queue (`asyncio.Queue`) for `add_episode` ensures sequential processing per `group_id`, preventing race conditions and keeping the API responsive.
*   **Dockerized Deployment:** Providing `Dockerfile` and `docker-compose.yml` simplifies setup and ensures consistency, especially for the Neo4j dependency.
*   **Client Abstraction:** The `GraphitiLLMConfig` and `GraphitiEmbedderConfig` classes abstract the creation of LLM and embedder clients, supporting both standard OpenAI and Azure OpenAI (including managed identity). 