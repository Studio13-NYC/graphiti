# Lessons Learned & Simplifications for Faster Rebuild

Based on the analysis of the `mcp_server` codebase, here are potential areas for simplification and lessons learned to accelerate a rebuild.

## Overengineered Areas / Potential Simplifications

1.  **Configuration Complexity:** While robust, the multi-layered Pydantic configuration (`GraphitiConfig` containing `GraphitiLLMConfig`, `GraphitiEmbedderConfig`, `Neo4jConfig`) loading from defaults, env vars, and CLI args could be simplified initially.
    *   **Shortcut:** Start with direct environment variable reading (`os.environ.get`) within the initialization logic for essential parameters (Neo4j creds, OpenAI key/model). Introduce Pydantic later if needed for validation and structure.
    *   **Shortcut:** Combine LLM and Embedder config into a single `OpenAIConfig` if only supporting OpenAI initially.

2.  **Azure OpenAI Support:** The logic to handle both standard OpenAI and Azure OpenAI (including managed identity and separate endpoints/deployments for LLM and embeddings) adds significant branching and complexity to client creation (`create_client`, `create_embedder_client`).
    *   **Shortcut:** Implement *only* standard OpenAI API key authentication first. Add Azure support later if specifically required.

3.  **Cross-Encoder Client:** The inclusion of a `CrossEncoderClient` (specifically `OpenAIRerankerClient`) adds another layer of configuration and potential dependency.
    *   **Shortcut:** Omit the cross-encoder initially. Rely on the default search/ranking provided by `graphiti-core`'s vector and keyword search. Add reranking later if search relevance needs improvement.

4.  **Search Config Logic (`search_nodes`):** Dynamically switching search configurations (`NODE_HYBRID_SEARCH_NODE_DISTANCE` vs. `NODE_HYBRID_SEARCH_RRF`) based on `center_node_uuid` adds complexity.
    *   **Shortcut:** Use one default hybrid search configuration (`NODE_HYBRID_SEARCH_RRF`) for all `search_nodes` calls initially.

## Unnecessary/Deferrable Features

1.  **Custom Entity Extraction (`Requirement`, `Preference`, `Procedure`):** The specific entity types (`Requirement`, `Preference`, `Procedure`) and the `--use-custom-entities` flag seem application-specific (possibly for the `_s13` variant).
    *   **Shortcut:** Rebuild the core server *without* these custom entity Pydantic models and the logic to pass them to `graphiti_client.add_episode`. Let `graphiti-core` handle generic entity extraction.

2.  **Server Variants (`_s13`, `_music`):** The presence of `graphiti_mcp_server_s13.py` and `graphiti_mcp_server_music.py`, which appear very similar to the main `graphiti_mcp_server.py`, suggests either code duplication or slightly different configurations that could likely be handled by parameters/config in a single script.
    *   **Shortcut:** Build *only one* server script (`server.py`). If variations are needed later, use configuration flags or separate config files rather than duplicating the entire script.

3.  **Detailed Formatting (`format_fact_result`, etc.):** While helpful, custom formatting functions for results can be simplified.
    *   **Shortcut:** Rely on Pydantic's `.model_dump(mode='json', exclude={...})` where possible for serialization within the tools, returning the resulting dict directly.

## Development Bottlenecks to Avoid

1.  **Complex Async Logic:** Implementing the `asyncio.Queue` for `add_episode` correctly can be tricky.
    *   **Mitigation:** Implement `add_episode` synchronously first to ensure the core Graphiti call works, then refactor to use the async queue.
2.  **Configuration Errors:** Debugging issues related to environment variables, CLI args, and Pydantic model validation can be time-consuming.
    *   **Mitigation:** Start simple with env vars, add clear logging during config loading, test configuration thoroughly at each stage.
3.  **Dependency Issues:** Ensuring compatible versions of Python, `graphiti-core`, `mcp`, Neo4j, etc.
    *   **Mitigation:** Use `uv sync` with a locked `uv.lock` file (generated after initial `uv sync`) or use the provided Docker setup for a consistent environment.

## Alternative Approaches for Speed

1.  **Leverage Docker Compose Heavily:** Use the provided `docker-compose.yml` not just for Neo4j but also for the MCP server itself from the start. This bypasses local Python environment setup issues.
2.  **Start with `stdio` Transport:** Debugging MCP communication is often easier over `stdio` than SSE initially. Get core tools working with `stdio`, then add SSE.
3.  **Focus on Core Tools:** Prioritize `add_episode`, `search_nodes`, and `search_facts`. Get these fully functional before implementing less critical tools like `delete_*`, `get_*`, `clear_graph`. 