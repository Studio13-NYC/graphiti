# Debugging Process: Failure to Save Custom Music Entities (Non-Streamlined Tools)

This document outlines the debugging steps taken to understand why saving custom music entities (e.g., `Album`) was failing when using the original, non-streamlined toolset in the Graphiti Music MCP server.

## 1. Problem Statement

Users were unable to successfully save custom music entities, such as Albums, using the dedicated MCP tools (e.g., `add_album`). Standard operations might have worked, but specific entity creation failed.

## 2. Context and Initial Setup

-   **Server Configuration:** The server (`mcp_server/music_server/server.py`) was launched with the `--use-custom-entities` flag enabled, but *without* the `--use-streamlined` flag.
-   **Tool Registration:** Based on the flags in `server.py`, this configuration registers tools from the following files:
    -   `tools.py` (Base Graphiti tools like `add_episode`, `search_nodes`)
    -   `music_tools.py` (Tools like `add_artist`, `add_album`)
    -   `music_tools_part2.py` (Tools like `add_track`, relationship helpers)
    -   `relationship_tools.py` (Tools for managing relationships)
-   **Excluded Tools:** The streamlined tools defined directly within `server.py` (`parse_and_store_music_data`, `add_entity`, `update_entity`, etc.) were *not* registered in this mode.

## 3. Key Observation (Startup Log Analysis)

The server startup log contained a critical warning:

```
2025-05-01 16:30:25,556 - mcp.server.fastmcp.tools.tool_manager - WARNING - Tool already exists: add_track
```

This indicated that a tool named `add_track` was being defined and registered more than once by the different files loaded during startup.

## 4. Investigation Steps

-   **Review Server Logic:** Examined `mcp_server/music_server/server.py` to confirm which tool registration functions were called based on the `--use-custom-entities` and lack of `--use-streamlined` flags.
-   **Inspect Tool Files:** Read the contents of `mcp_server/music_server/music_tools_part2.py` and `mcp_server/music_server/music_tools.py` to locate the definitions of potentially conflicting tools (`add_track`) and the target tool (`add_album`).

## 5. Findings

-   **`add_track` Conflict Confirmed:** `music_tools_part2.py` defines an `add_track` tool. The conflict warning means another registered file (likely `tools.py` or another specialized tool file) also defines a tool with the exact same name.
-   **`add_album` Implementation Analysis:** `music_tools.py` defines the `add_album` tool. The implementation correctly attempts to signal the custom entity type to `graphiti-core` by passing `entity_types={"Album": Album}` within its call to `graphiti_client.add_episode`. In isolation, this part of the logic appears correct.

## 6. Hypothesis and Conclusion

Despite the `add_album` implementation seeming plausible, the **root cause of the failure is the tool registration conflict identified by the `add_track` warning.**

-   **Mechanism:** When multiple tools with the same name are registered, the MCP framework's behavior becomes unpredictable. It might overwrite previous registrations, corrupt internal state, or fail to dispatch calls correctly.
-   **Impact:** Even if `add_album` itself is not duplicated, the conflict involving `add_track` likely destabilizes the entire tool registry for tools defined in the `music_tools*` files, preventing `add_album` (and potentially others) from executing reliably.
-   **Contrast with Streamlined:** The `--use-streamlined` approach (using `add_entity` defined in `server.py`) avoids this by:
    1.  Conditionally registering a distinct set of tools.
    2.  Consolidating entity logic, inherently preventing self-conflict.
    3.  Explicitly using the `MUSIC_ENTITY_TYPES` map provided during initialization.

## 7. Recommended Fix

To enable the non-streamlined, custom entity tools (`add_album`, `add_artist`, etc.) to function correctly:

1.  **Identify All Conflicts:** Thoroughly search `tools.py`, `music_tools.py`, `music_tools_part2.py`, and `relationship_tools.py` to find *all* instances of duplicate tool names.
2.  **Resolve Conflicts:** Choose a single, canonical implementation for each duplicated tool name. Remove or rename the conflicting definitions in the other files. For example, if a generic `add_track` exists in `tools.py`, the one in `music_tools_part2.py` should likely be removed or renamed (e.g., `add_music_track`).
3.  **Verify `entity_types` Usage:** Ensure all tools in the `music_tools*` files intended to create custom entities correctly pass the `entity_types` dictionary (mapping the type string to the corresponding Pydantic model) in their calls to `graphiti_client.add_episode`.

## 8. Decision: Removal of Streamlined Approach (May 1, 2025)

Given the persistent issues encountered with the `--use-streamlined` flag (including initial server launch failures and the complexity it added relative to the original, working approach), the decision was made to entirely remove the streamlined toolset from `mcp_server/music_server/server.py`.

**Changes Made:**

-   Removed the `--use-streamlined` command-line argument.
-   Removed the `register_streamlined_tools` function and all associated tool definitions (`parse_and_store_music_data`, `add_entity`, `update_entity`, `delete_entity`, `get_entity`, `create_relationship`, `get_relationships`, `search_entities`) from `server.py`.
-   Modified the `main` function in `server.py` to remove the conditional logic based on `--use-streamlined`.
-   The server now *always* registers the tools from `music_tools.py`, `music_tools_part2.py`, and `relationship_tools.py` whenever the `--use-custom-entities` flag is enabled.

**Rationale:**

-   Simplifies the codebase by removing a parallel, problematic implementation path.
-   Focuses efforts on ensuring the stability and correctness of the original, separate tool files (`music_tools*`, `relationship_tools*`).
-   Aligns with the user preference for the original, more granular tools which were previously functional.

**Next Step:** After this removal, the immediate focus should be on resolving any remaining tool name conflicts within the non-streamlined tool files (`music_tools.py`, `music_tools_part2.py`, `relationship_tools.py`, `tools.py`) as identified in step 7.

## 9. Conflict Resolution: `add_track` (May 1, 2025)

Following the removal of the streamlined approach, the next step was to resolve the identified tool conflicts.

-   **Conflict:** The startup warning `Tool already exists: add_track` confirmed that the `add_track` tool defined in `mcp_server/music_server/music_tools_part2.py` conflicted with another tool registration (likely from the base tools registered via `tools.py`).
-   **Resolution:** The `add_track` tool definition was removed entirely from `mcp_server/music_server/music_tools_part2.py`.
-   **Rationale:** This resolves the immediate conflict. It assumes that adding individual tracks might be handled through relationships (e.g., `add_track_to_album`) or via the generic `add_episode` tool from the base registration. Keeping the specialized `add_track` would require renaming it to avoid collision with potentially essential base tools.

**Further Steps:**

-   Restart the server and check if the `add_track` warning disappears.
-   Observe if any *new* tool conflict warnings appear in the logs, indicating other name collisions between the base tools (`tools.py`) and the specialized music/relationship tools (`music_tools.py`, `music_tools_part2.py`, `relationship_tools.py`).
-   Test the functionality of adding custom entities (e.g., `add_album`, `add_artist`) to ensure the original problem is resolved now that the tool registry is potentially stable.

## 10. Testing Custom Entity Tools (`add_artist`, `add_album`) (May 1, 2025)

With the `add_track` conflict resolved and no other warnings present, the specific tools for adding custom entities were tested.

-   **Test 1: `add_artist`**
    -   **Call:** `mcp_Graphiti-Music_add_artist(name="Test Artist Gemini", genres="Synth-Pop, Experimental", group_id="s13-music")`
    -   **Result:** Failed
    -   **Error:** `Error calling tool: Parameter 'genres' must be of type undefined, got string`

-   **Test 2: `add_album`**
    -   **Call:** `mcp_Graphiti-Music_add_album(title="Test Album Gemini", album_type="Studio", group_id="s13-music")`
    -   **Result:** Failed
    -   **Error:** `Error calling tool: Parameter 'album_type' must be of type undefined, got string`

**Analysis:**

Both attempts failed with a similar error pattern, indicating a type mismatch problem specifically with string parameters provided to these tools.

-   **Problem:** The tools (`add_artist`, `add_album` in `music_tools.py`) expect certain arguments as simple strings (e.g., comma-separated `genres` or `album_type`), process them internally (e.g., `genres.split(',')`), and then package the data into a JSON string passed to `graphiti_client.add_episode` along with `entity_types={"Artist": Artist}` or `entity_types={"Album": Album}`.
-   **Error Symptom:** The error message `Parameter '...' must be of type undefined, got string` is unusual. It suggests that during the tool call process (potentially at the MCP layer or during `graphiti-core`'s internal validation when `entity_types` is specified), the type information for these string parameters is being lost or misinterpreted.
-   **Possible Causes:**
    1.  **MCP Signature Mismatch:** The tool signature visible to the client might incorrectly define these parameters.
    2.  **Pydantic Validation:** The interaction between the JSON `episode_body` created by the tool and the Pydantic validation triggered by `entity_types` within `graphiti-core` might be failing.
    3.  **Tool Logic:** A subtle bug in the tool's data preparation logic.

**Conclusion:** The issue is not simply the tool conflict (which was resolved), but likely lies in the way these specific wrapper tools (`add_artist`, `add_album`) interact with the underlying `graphiti_client.add_episode` method when specifying `entity_types`.

**Next Step:** To isolate the problem, the plan is to bypass the specific `add_artist`/`add_album` wrapper tools and call the base `add_episode` tool directly, mimicking how the wrapper tools *attempt* to construct the call. This will help determine if the fault lies within the wrapper tools themselves or in the `graphiti_client.add_episode` handling of JSON bodies with `entity_types`. 

## 11. Debugging Plan: `add_artist`/`add_album` Type Error (May 2, 2025)

**Goal:** Identify why calls to MCP tools like `add_artist` fail with a type error (`Parameter '...' must be of type undefined, got string`) when attempting to save custom entities via `graphiti_client.add_episode` using the `entity_types` parameter.

**Approach:** Trace the execution flow step-by-step from the MCP tool call down to the `graphiti-core` processing, examining the data and types at each stage.

**Plan Steps:**

1.  **Analyze the MCP Tool (`add_artist`) Implementation:**
    *   **Goal:** Understand precisely how the `add_artist` tool prepares its data before calling the Graphiti client.
    *   **Action:** Read the source code of the `add_artist` function within `mcp_server/music_server/music_tools.py`. Pay close attention to how incoming arguments are received, how the `episode_body` dictionary is constructed and serialized (e.g., to JSON), and how the `entity_types={"Artist": Artist}` dictionary is passed to `graphiti_client.add_episode`.

2.  **Trace the `graphiti_client.add_episode` Call:**
    *   **Goal:** See how the `graphiti-client` library packages the `episode_body` and `entity_types` information into an HTTP request for `graphiti-core`.
    *   **Action:** Examine the `add_episode` method within the `graphiti-client` library code. Check how `episode_body` and `entity_types` are included in the request payload and if any client-side transformations occur.

3.  **Inspect the `graphiti-core` API Endpoint:**
    *   **Goal:** Understand how the `graphiti-core` server receives the API call, parses the payload, and uses `entity_types` to trigger Pydantic validation.
    *   **Action:** Examine the relevant API endpoint handler in the `graphiti-core` codebase. Analyze how the request payload is parsed, how the Pydantic model (e.g., `Artist`) is selected based on `entity_types`, and how the `episode_body` data is validated against that model. **This is the most likely location of the `undefined` type error.**

4.  **Identify Discrepancy and Formulate Fix:**
    *   **Goal:** Pinpoint the exact step where data/type interpretation fails.
    *   **Action:** Determine if the issue lies in the `add_artist` tool's formatting, `graphiti-client` transmission, or `graphiti-core` parsing/validation. Propose a specific code change.

5.  **Verify the Fix:**
    *   **Goal:** Confirm the error is resolved.
    *   **Action:** Re-run the failing MCP call (`mcp_Graphiti-Music_add_artist`) and verify successful completion and entity creation. 