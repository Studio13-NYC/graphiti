import asyncio
import logging
import json
import uuid # Import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Union, List, Dict, cast, TypedDict # Import TypedDict

from mcp.server.fastmcp import FastMCP # Needed for @mcp.tool decorator
from pydantic import BaseModel

# Assuming graphiti_core is installed and accessible
from graphiti_core import Graphiti
from graphiti_core.edges import EntityEdge
from graphiti_core.nodes import EpisodeType, EpisodicNode
from graphiti_core.search.search_config_recipes import (
    NODE_HYBRID_SEARCH_NODE_DISTANCE,
    NODE_HYBRID_SEARCH_RRF,
)
from graphiti_core.search.search_filters import SearchFilters
from graphiti_core.utils.maintenance.graph_data_operations import clear_data

# Import models from the local models package
from .models.music import (
    Requirement, Preference, Procedure, # Base types (optional)
    Artist, Album, Track, Equipment, Studio, Person, Credit, Label, Performance, Effect
)

# Import config types (assuming they are needed globally or passed)
# If config and graphiti_client are passed to tools, these imports might not be needed here
from .config import GraphitiConfig

logger = logging.getLogger(__name__)

# --- Globals (Consider passing these to tools instead) ---
# These would be set by server.py after initialization
graphiti_client_instance: Optional[Graphiti] = None
config_instance: Optional[GraphitiConfig] = None
mcp_instance: Optional[FastMCP] = None # Needed for decorator if tools are in separate file

# --- Entity Type Mapping --- 
# This dictionary maps the string label (used in Neo4j) to the Pydantic model.
# Graphiti uses this when `use_custom_entities` is enabled.
MUSIC_ENTITY_TYPES: Dict[str, BaseModel] = {
    # Base Types (Include if desired)
    'Requirement': Requirement,  # type: ignore
    'Preference': Preference,  # type: ignore
    'Procedure': Procedure,  # type: ignore
    # Music Types
    'Artist': Artist,
    'Album': Album,
    'Track': Track,
    'Equipment': Equipment,
    'Studio': Studio,
    'Person': Person,
    'Credit': Credit,
    'Label': Label,
    'Performance': Performance,
    'Effect': Effect,
}

# --- Type Definitions for Tool Responses --- 
# (These could also go in a separate types.py)
class ErrorResponse(TypedDict): # Reverted to TypedDict for explicit structure
    error: str

class SuccessResponse(TypedDict):
    message: str

class NodeResult(TypedDict):
    uuid: str
    name: str
    summary: str
    labels: List[str]
    group_id: str
    created_at: str
    attributes: Dict[str, Any]

class NodeSearchResponse(TypedDict):
    message: str
    nodes: List[NodeResult]

class FactSearchResponse(TypedDict):
    message: str
    facts: List[Dict[str, Any]]

class EpisodeSearchResponse(TypedDict):
    message: str
    episodes: List[Dict[str, Any]]

# --- Helper Functions --- 

def format_fact_result(edge: EntityEdge) -> Dict[str, Any]:
    """Format an entity edge into a readable result, excluding embedding."""
    return edge.model_dump(
        mode='json',
        exclude={'fact_embedding'},
    )

# --- Episode Processing Queue --- 
# (Moved here as it's closely tied to add_episode tool)
episode_queues: Dict[str, asyncio.Queue] = {}
queue_workers: Dict[str, bool] = {}

async def process_episode_queue(group_id: str):
    """Process episodes for a specific group_id sequentially."""
    global queue_workers, graphiti_client_instance, config_instance

    # This function needs access to graphiti_client and config
    if not graphiti_client_instance or not config_instance:
        logger.error(f"Queue worker {group_id}: Graphiti client or config not initialized!")
        # Decide how to handle this - maybe clear the worker flag and exit?
        queue_workers[group_id] = False
        return

    logger.info(f'Starting episode queue worker for group_id: {group_id}')
    queue_workers[group_id] = True

    try:
        while True:
            process_func = await episode_queues[group_id].get()
            try:
                # Pass necessary context if the process_func requires it
                await process_func(graphiti_client_instance, config_instance)
            except Exception as e:
                logger.error(f'Error processing queued episode for group_id {group_id}: {e}')
            finally:
                episode_queues[group_id].task_done()
    except asyncio.CancelledError:
        logger.info(f'Episode queue worker for group_id {group_id} was cancelled')
    except Exception as e:
        logger.error(f'Unexpected error in queue worker for group_id {group_id}: {e}')
    finally:
        queue_workers[group_id] = False
        logger.info(f'Stopped episode queue worker for group_id: {group_id}')

# --- MCP Tool Definitions --- 

def register_tools(mcp: FastMCP, graphiti_client: Graphiti, config: GraphitiConfig):
    """Registers all MCP tools with the FastMCP instance."""
    global graphiti_client_instance, config_instance, mcp_instance
    graphiti_client_instance = graphiti_client
    config_instance = config
    mcp_instance = mcp

    # Using global mcp_instance for decorators (simpler for now)
    if not mcp_instance:
         raise ValueError("MCP instance not set before registering tools")

    @mcp_instance.tool()
    async def add_track(
        title: str,
        duration_ms: Optional[str] = None,
        explicit: Optional[str] = None,
        popularity: Optional[str] = None,
        preview_url: Optional[str] = None,
        isrc: Optional[str] = None,
        lyrics: Optional[str] = None,
        tempo: Optional[str] = None,
        key: Optional[str] = None,
        genre: Optional[str] = None,
        spotify_uri: Optional[str] = None,
        spotify_url: Optional[str] = None,
        artist_name: Optional[str] = None,
        album_title: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> Union[SuccessResponse, ErrorResponse]:
        """Add a new track, optionally linking to Artist and Album."""
        client = graphiti_client_instance
        cfg = config_instance
        if not client or not cfg:
            return ErrorResponse(error='Server not initialized')

        effective_group_id = group_id if group_id is not None else cfg.group_id
        if not effective_group_id:
             return ErrorResponse(error='group_id must be provided or set in config')
        group_id_str = str(effective_group_id)

        try:
            # Convert string inputs to correct types
            track_data = {
                'title': title,
                'duration_ms': int(duration_ms) if duration_ms else None,
                'explicit': explicit.lower() == 'true' if explicit else None,
                'popularity': int(popularity) if popularity else None,
                'preview_url': preview_url,
                'isrc': isrc,
                'lyrics': lyrics,
                'tempo': float(tempo) if tempo else None,
                'key': key,
                'genre': genre,
                'spotify_uri': spotify_uri,
                'spotify_url': spotify_url,
            }
            track_data_filtered = {k: v for k, v in track_data.items() if v is not None}

            episode_uuid = uuid.uuid4()
            track_episode = EpisodicNode(
                 uuid=str(episode_uuid),
                 name=f"Track: {title}",
                 source=EpisodeType.json,
                 source_description="add_track tool",
                 episode_body=json.dumps({"Track": track_data_filtered}),
                 group_id=group_id_str,
                 reference_time=datetime.now(timezone.utc)
            )
            await client.add_episode_node(track_episode, entity_types=MUSIC_ENTITY_TYPES if cfg.use_custom_entities else {})
            logger.info(f"Track node '{title}' added via episode {episode_uuid}")

            # Relationship creation logic needs improvement/verification with graphiti-core capabilities
            # ...

            return SuccessResponse(message=f'Track \'{title}\' added successfully (relationships pending improvement)')

        except Exception as e:
            logger.error(f'Error adding track: {e}')
            return ErrorResponse(error=f'Error adding track: {str(e)}')

    @mcp_instance.tool()
    async def add_episode(
        name: str,
        episode_body: str,
        group_id: Optional[str] = None,
        source: str = 'text',
        source_description: str = '',
        uuid_str: Optional[str] = None,
    ) -> Union[SuccessResponse, ErrorResponse]:
        """Add an episode (text, json, message) to the knowledge graph."""
        client = graphiti_client_instance
        cfg = config_instance
        if not client or not cfg:
            return ErrorResponse(error='Server not initialized')

        try:
            source_type = EpisodeType.text
            if source.lower() == 'message': source_type = EpisodeType.message
            elif source.lower() == 'json': source_type = EpisodeType.json

            effective_group_id = group_id if group_id is not None else cfg.group_id
            if not effective_group_id:
                 return ErrorResponse(error='group_id must be provided or set in config')
            group_id_str = str(effective_group_id)

            async def process_episode_task(proc_client: Graphiti, proc_cfg: GraphitiConfig):
                try:
                    logger.info(f"Processing queued episode '{name}' for group_id: {group_id_str}")
                    entity_types_to_use = MUSIC_ENTITY_TYPES if proc_cfg.use_custom_entities else {}

                    await proc_client.add_episode(
                        name=name,
                        episode_body=episode_body,
                        source=source_type,
                        source_description=source_description,
                        group_id=group_id_str,
                        uuid=uuid_str,
                        reference_time=datetime.now(timezone.utc),
                        entity_types=entity_types_to_use,
                    )
                    logger.info(f"Episode '{name}' added successfully")

                except Exception as e:
                    logger.error(f"Error processing episode '{name}' in queue: {e}")

            if group_id_str not in episode_queues:
                episode_queues[group_id_str] = asyncio.Queue()

            await episode_queues[group_id_str].put(process_episode_task)

            if not queue_workers.get(group_id_str, False):
                asyncio.create_task(process_episode_queue(group_id_str))

            return SuccessResponse(message=f"Episode '{name}' queued (queue size: {episode_queues[group_id_str].qsize()})") # Fixed parenthesis
        except Exception as e:
            logger.error(f'Error queuing episode: {e}')
            return ErrorResponse(error=f'Error queuing episode: {str(e)}')


    @mcp_instance.tool()
    async def search_nodes(
        query: str,
        group_ids: Optional[List[str]] = None,
        max_nodes: int = 10,
        center_node_uuid: Optional[str] = None,
        entity: str = '', # Label filter
    ) -> Union[NodeSearchResponse, ErrorResponse]:
        """Search for node summaries, optionally filtering by label."""
        client = graphiti_client_instance
        cfg = config_instance
        if not client or not cfg:
            return ErrorResponse(error='Server not initialized')

        try:
            effective_group_ids = group_ids if group_ids is not None else [cfg.group_id] if cfg.group_id else []
            if not effective_group_ids:
                 return ErrorResponse(error='No group_ids specified for search')

            search_config = NODE_HYBRID_SEARCH_RRF.model_copy(deep=True)
            if center_node_uuid:
                search_config = NODE_HYBRID_SEARCH_NODE_DISTANCE.model_copy(deep=True)
            search_config.limit = max_nodes

            filters = SearchFilters()
            if entity != '':
                filters.node_labels = [entity]

            search_results = await client._search(
                query=query,
                config=search_config,
                group_ids=effective_group_ids,
                center_node_uuid=center_node_uuid,
                search_filter=filters,
            )

            if not search_results.nodes:
                return NodeSearchResponse(message='No relevant nodes found', nodes=[])

            formatted_nodes: List[NodeResult] = [
                {
                    'uuid': node.uuid,
                    'name': node.name,
                    'summary': getattr(node, 'summary', ''),
                    'labels': getattr(node, 'labels', []),
                    'group_id': node.group_id,
                    'created_at': node.created_at.isoformat(),
                    'attributes': getattr(node, 'attributes', {}),
                }
                for node in search_results.nodes
            ]
            return NodeSearchResponse(message='Nodes retrieved', nodes=formatted_nodes)
        except Exception as e:
            logger.error(f'Error searching nodes: {e}')
            return ErrorResponse(error=f'Error searching nodes: {str(e)}')

    @mcp_instance.tool()
    async def search_facts(
        query: str,
        group_ids: Optional[List[str]] = None,
        max_facts: int = 10,
        center_node_uuid: Optional[str] = None,
    ) -> Union[FactSearchResponse, ErrorResponse]:
        """Search the Graphiti knowledge graph for relevant facts."""
        client = graphiti_client_instance
        cfg = config_instance
        if not client or not cfg:
            return ErrorResponse(error='Server not initialized')

        try:
            effective_group_ids = group_ids if group_ids is not None else [cfg.group_id] if cfg.group_id else []
            if not effective_group_ids:
                 return ErrorResponse(error='No group_ids specified for search')

            relevant_edges = await client.search(
                group_ids=effective_group_ids,
                query=query,
                num_results=max_facts,
                center_node_uuid=center_node_uuid,
            )

            if not relevant_edges:
                return FactSearchResponse(message='No relevant facts found', facts=[])

            facts = [format_fact_result(edge) for edge in relevant_edges]
            return FactSearchResponse(message='Facts retrieved successfully', facts=facts)
        except Exception as e:
            logger.error(f'Error searching facts: {e}')
            return ErrorResponse(error=f'Error searching facts: {str(e)}')

    @mcp_instance.tool()
    async def delete_entity_edge(uuid_str: str) -> Union[SuccessResponse, ErrorResponse]:
        """Delete an entity edge from the Graphiti knowledge graph."""
        client = graphiti_client_instance
        if not client:
            return ErrorResponse(error='Server not initialized')
        try:
            entity_edge = await EntityEdge.get_by_uuid(client.driver, uuid_str)
            await entity_edge.delete(client.driver)
            return SuccessResponse(message=f'Entity edge {uuid_str} deleted')
        except Exception as e:
            logger.error(f'Error deleting edge {uuid_str}: {e}')
            return ErrorResponse(error=f'Error deleting edge {uuid_str}: {str(e)}')

    @mcp_instance.tool()
    async def delete_episode(uuid_str: str) -> Union[SuccessResponse, ErrorResponse]:
        """Delete an episode from the Graphiti knowledge graph."""
        client = graphiti_client_instance
        if not client:
            return ErrorResponse(error='Server not initialized')
        try:
            episodic_node = await EpisodicNode.get_by_uuid(client.driver, uuid_str)
            await episodic_node.delete(client.driver)
            return SuccessResponse(message=f'Episode {uuid_str} deleted')
        except Exception as e:
            logger.error(f'Error deleting episode {uuid_str}: {e}')
            return ErrorResponse(error=f'Error deleting episode {uuid_str}: {str(e)}')

    @mcp_instance.tool()
    async def get_entity_edge(uuid_str: str) -> Union[Dict[str, Any], ErrorResponse]:
        """Get an entity edge by its UUID."""
        client = graphiti_client_instance
        if not client:
            return ErrorResponse(error='Server not initialized')
        try:
            entity_edge = await EntityEdge.get_by_uuid(client.driver, uuid_str)
            return format_fact_result(entity_edge)
        except Exception as e:
            logger.error(f'Error getting edge {uuid_str}: {e}')
            return ErrorResponse(error=f'Error getting edge {uuid_str}: {str(e)}')

    @mcp_instance.tool()
    async def get_episodes(
        group_id: Optional[str] = None, last_n: int = 10
    ) -> Union[List[Dict[str, Any]], EpisodeSearchResponse, ErrorResponse]:
        """Get the most recent episodes for a specific group."""
        client = graphiti_client_instance
        cfg = config_instance
        if not client or not cfg:
            return ErrorResponse(error='Server not initialized')

        try:
            effective_group_id = group_id if group_id is not None else cfg.group_id
            if not effective_group_id:
                 return ErrorResponse(error='group_id must be provided or set in config')

            episodes = await client.retrieve_episodes(
                group_ids=[str(effective_group_id)],
                last_n=last_n,
                reference_time=datetime.now(timezone.utc)
            )

            if not episodes:
                return EpisodeSearchResponse(message=f'No episodes found for group {effective_group_id}', episodes=[])

            formatted_episodes = [ep.model_dump(mode='json') for ep in episodes]
            return formatted_episodes # MCP handles list serialization
        except Exception as e:
            logger.error(f'Error getting episodes: {e}')
            return ErrorResponse(error=f'Error getting episodes: {str(e)}')

    @mcp_instance.tool()
    async def clear_graph() -> Union[SuccessResponse, ErrorResponse]:
        """Clear all data from the graph and rebuild indices."""
        client = graphiti_client_instance
        if not client:
            return ErrorResponse(error='Server not initialized')
        try:
            await clear_data(client.driver)
            await client.build_indices_and_constraints()
            return SuccessResponse(message='Graph cleared and indices rebuilt')
        except Exception as e:
            logger.error(f'Error clearing graph: {e}')
            return ErrorResponse(error=f'Error clearing graph: {str(e)}')

    @mcp_instance.tool(name="get_status")
    async def get_status_tool() -> Dict[str, str]:
        """Get the status of the server and Neo4j connection."""
        client = graphiti_client_instance
        if not client:
            return {'status': 'error', 'message': 'Graphiti client not initialized'}
        try:
            await client.driver.verify_connectivity()
            return {'status': 'ok', 'message': 'Running and connected to Neo4j'}
        except Exception as e:
            logger.error(f'Neo4j connection check failed: {e}')
            return {'status': 'error', 'message': f'Neo4j connection failed: {str(e)}'}

    logger.info("Graphiti MCP tools registered.") 