#!/usr/bin/env python3
"""
Graphiti MCP Server - Exposes Graphiti functionality through the Model Context Protocol (MCP)
"""

import argparse
import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict, Union, cast
import json

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from graphiti_core import Graphiti
from graphiti_core.edges import EntityEdge
from graphiti_core.llm_client import LLMClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.nodes import EpisodeType, EpisodicNode
from graphiti_core.search.search_config_recipes import (
    NODE_HYBRID_SEARCH_NODE_DISTANCE,
    NODE_HYBRID_SEARCH_RRF,
)
from graphiti_core.search.search_filters import SearchFilters
from graphiti_core.utils.maintenance.graph_data_operations import clear_data

load_dotenv()

DEFAULT_LLM_MODEL = 'gpt-4o'


class Requirement(BaseModel):
    """A Requirement represents a specific need, feature, or functionality that a product or service must fulfill.

    Always ensure an edge is created between the requirement and the project it belongs to, and clearly indicate on the
    edge that the requirement is a requirement.

    Instructions for identifying and extracting requirements:
    1. Look for explicit statements of needs or necessities ("We need X", "X is required", "X must have Y")
    2. Identify functional specifications that describe what the system should do
    3. Pay attention to non-functional requirements like performance, security, or usability criteria
    4. Extract constraints or limitations that must be adhered to
    5. Focus on clear, specific, and measurable requirements rather than vague wishes
    6. Capture the priority or importance if mentioned ("critical", "high priority", etc.)
    7. Include any dependencies between requirements when explicitly stated
    8. Preserve the original intent and scope of the requirement
    9. Categorize requirements appropriately based on their domain or function
    """

    project_name: str = Field(
        ...,
        description='The name of the project to which the requirement belongs.',
    )
    description: str = Field(
        ...,
        description='Description of the requirement. Only use information mentioned in the context to write this description.',
    )


class Preference(BaseModel):
    """A Preference represents a user's expressed like, dislike, or preference for something.

    Instructions for identifying and extracting preferences:
    1. Look for explicit statements of preference such as "I like/love/enjoy/prefer X" or "I don't like/hate/dislike X"
    2. Pay attention to comparative statements ("I prefer X over Y")
    3. Consider the emotional tone when users mention certain topics
    4. Extract only preferences that are clearly expressed, not assumptions
    5. Categorize the preference appropriately based on its domain (food, music, brands, etc.)
    6. Include relevant qualifiers (e.g., "likes spicy food" rather than just "likes food")
    7. Only extract preferences directly stated by the user, not preferences of others they mention
    8. Provide a concise but specific description that captures the nature of the preference
    """

    category: str = Field(
        ...,
        description="The category of the preference. (e.g., 'Brands', 'Food', 'Music')",
    )
    description: str = Field(
        ...,
        description='Brief description of the preference. Only use information mentioned in the context to write this description.',
    )


class Procedure(BaseModel):
    """A Procedure informing the agent what actions to take or how to perform in certain scenarios. Procedures are typically composed of several steps.

    Instructions for identifying and extracting procedures:
    1. Look for sequential instructions or steps ("First do X, then do Y")
    2. Identify explicit directives or commands ("Always do X when Y happens")
    3. Pay attention to conditional statements ("If X occurs, then do Y")
    4. Extract procedures that have clear beginning and end points
    5. Focus on actionable instructions rather than general information
    6. Preserve the original sequence and dependencies between steps
    7. Include any specified conditions or triggers for the procedure
    8. Capture any stated purpose or goal of the procedure
    9. Summarize complex procedures while maintaining critical details
    """

    description: str = Field(
        ...,
        description='Brief description of the procedure. Only use information mentioned in the context to write this description.',
    )

# ── Custom music‑domain entities (added) ────────────────────────────────────
class Artist(BaseModel):
    """An individual musician or group"""
    name: str = Field(..., description="Artist name")
    biography: Optional[str] = Field(None, description="Artist biography")
    genres: Optional[list[str]] = Field(None, description="List of musical genres")
    active_years: Optional[str] = Field(None, description="Active years active")
    country: Optional[str] = Field(None, description="Country of origin")
    image_url: Optional[str] = Field(None, description="Image URL")
    influences: Optional[list[str]] = Field(None, description="Influences")
    popularity: Optional[int] = Field(None, description="Popularity 0‑100")
    followers: Optional[int] = Field(None, description="Followers")
    spotify_uri: Optional[str] = Field(None, description="Spotify URI")
    spotify_url: Optional[str] = Field(None, description="Spotify URL")


class Album(BaseModel):
    """Album"""
    title: str = Field(..., description="Album title")
    release_date: Optional[str] = Field(None, description="Release date")
    album_type: Optional[str] = Field(None, description="Album type")
    total_tracks: Optional[int] = Field(None, description="Track count")
    catalog_number: Optional[str] = Field(None, description="Catalog number")
    images: Optional[list[dict[str, str]]] = Field(None, description="Artwork URLs")
    release_date_precision: Optional[str] = Field(None, description="Date precision")
    spotify_uri: Optional[str] = Field(None, description="Spotify URI")
    spotify_url: Optional[str] = Field(None, description="Spotify URL")


class Track(BaseModel):
    """Song or piece"""
    title: str = Field(..., description="Track title")
    duration_ms: Optional[int] = Field(None, description="Duration in ms")
    explicit: Optional[bool] = Field(None, description="Explicit content?")
    popularity: Optional[int] = Field(None, description="Popularity 0‑100")
    preview_url: Optional[str] = Field(None, description="Preview URL")
    isrc: Optional[str] = Field(None, description="ISRC code")
    lyrics: Optional[str] = Field(None, description="Lyrics")
    tempo: Optional[float] = Field(None, description="Tempo (BPM)")
    key: Optional[str] = Field(None, description="Musical key")
    genre: Optional[str] = Field(None, description="Genre")
    spotify_uri: Optional[str] = Field(None, description="Spotify URI")
    spotify_url: Optional[str] = Field(None, description="Spotify URL")


class Equipment(BaseModel):
    """Instrument or gear"""
    name: str = Field(..., description="Equipment name")
    type: Optional[str] = Field(None, description="Type")
    manufacturer: Optional[str] = Field(None, description="Manufacturer")
    model: Optional[str] = Field(None, description="Model designation")
    year: Optional[int] = Field(None, description="Year of manufacture")
    specifications: Optional[dict[str, str | int | float]] = Field(None, description="Specs")
    notable_users: Optional[list[str]] = Field(None, description="Notable users")


class Studio(BaseModel):
    """Recording studio"""
    name: str = Field(..., description="Studio name")
    location: Optional[str] = Field(None, description="Location")
    founding_date: Optional[str] = Field(None, description="Founded")
    specifications: Optional[dict[str, str | int | float]] = Field(None, description="Specs")
    notable_recordings: Optional[list[str]] = Field(None, description="Notable recordings")


class Person(BaseModel):
    """Producer, engineer, etc."""
    name: str = Field(..., description="Name")
    roles: Optional[list[str]] = Field(None, description="Roles" )
    biography: Optional[str] = Field(None, description="Biography")
    specialties: Optional[list[str]] = Field(None, description="Specialties")
    notable_works: Optional[list[str]] = Field(None, description="Notable works")


class Credit(BaseModel):
    """Specific credit role"""
    role_name: str = Field(..., description="Role name")
    contribution_details: Optional[str] = Field(None, description="Contribution details")
    primary_credit: Optional[bool] = Field(None, description="Primary credit?")
    contribution_percentage: Optional[float] = Field(None, description="Royalty %")


class Label(BaseModel):
    """Music label"""
    name: str = Field(..., description="Label name")
    founding_date: Optional[str] = Field(None, description="Founded")
    parent_company: Optional[str] = Field(None, description="Parent company")
    roster: Optional[list[str]] = Field(None, description="Roster")
    genre_focus: Optional[list[str]] = Field(None, description="Genre focus")


class Performance(BaseModel):
    """Live show"""
    venue: str = Field(..., description="Venue")
    date: Optional[str] = Field(None, description="Date")
    setlist: Optional[list[str]] = Field(None, description="Setlist" )
    lineup: Optional[list[str]] = Field(None, description="Line‑up")
    recordings: Optional[list[str]] = Field(None, description="Recordings")


class Effect(BaseModel):
    """Audio effect or processor"""
    name: str = Field(..., description="Effect name")
    type: Optional[str] = Field(None, description="Effect type")
    parameters: Optional[dict[str, str | int | float]] = Field(None, description="Parameters")
    position: Optional[str] = Field(None, description="Position in chain")
    context: Optional[str] = Field(None, description="Usage context")



ENTITY_TYPES: dict[str, BaseModel] = {
    'Requirement': Requirement,  # type: ignore
    'Preference': Preference,  # type: ignore
    'Procedure': Procedure,  # type: ignore
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


# Type definitions for API responses
class ErrorResponse(TypedDict):
    error: str


class SuccessResponse(TypedDict):
    message: str


class NodeResult(TypedDict):
    uuid: str
    name: str
    summary: str
    labels: list[str]
    group_id: str
    created_at: str
    attributes: dict[str, Any]


class NodeSearchResponse(TypedDict):
    message: str
    nodes: list[NodeResult]


class FactSearchResponse(TypedDict):
    message: str
    facts: list[dict[str, Any]]


class EpisodeSearchResponse(TypedDict):
    message: str
    episodes: list[dict[str, Any]]


class StatusResponse(TypedDict):
    status: str
    message: str


# Server configuration classes
class GraphitiConfig(BaseModel):
    """Configuration for Graphiti client.

    Centralizes all configuration parameters for the Graphiti client,
    including database connection details and LLM settings.
    """

    neo4j_uri: str = 'bolt://localhost:7687'
    neo4j_user: str = 'neo4j'
    neo4j_password: str = 'password'
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    model_name: Optional[str] = None
    group_id: Optional[str] = None
    use_custom_entities: bool = False

    @classmethod
    def from_env(cls) -> 'GraphitiConfig':
        """Create a configuration instance from environment variables."""
        return cls(
            neo4j_uri=os.environ.get('NEO4J_URI', 'bolt://localhost:7687'),
            neo4j_user=os.environ.get('NEO4J_USER', 'neo4j'),
            neo4j_password=os.environ.get('NEO4J_PASSWORD', 'password'),
            openai_api_key=os.environ.get('OPENAI_API_KEY'),
            openai_base_url=os.environ.get('OPENAI_BASE_URL'),
            model_name=os.environ.get('MODEL_NAME'),
        )


class MCPConfig(BaseModel):
    """Configuration for MCP server."""

    transport: str


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Create global config instance
config = GraphitiConfig.from_env()

# MCP server instructions
GRAPHITI_MCP_INSTRUCTIONS = """
Welcome to Graphiti MCP - a memory service for AI agents built on a knowledge graph. Graphiti performs well
with dynamic data such as user interactions, changing enterprise data, and external information.

Graphiti transforms information into a richly connected knowledge network, allowing you to 
capture relationships between concepts, entities, and information. The system organizes data as episodes 
(content snippets), nodes (entities), and facts (relationships between entities), creating a dynamic, 
queryable memory store that evolves with new information. Graphiti supports multiple data formats, including 
structured JSON data, enabling seamless integration with existing data pipelines and systems.

Facts contain temporal metadata, allowing you to track the time of creation and whether a fact is invalid 
(superseded by new information).

Key capabilities:
1. Add episodes (text, messages, or JSON) to the knowledge graph with the add_episode tool
2. Search for nodes (entities) in the graph using natural language queries with search_nodes
3. Find relevant facts (relationships between entities) with search_facts
4. Retrieve specific entity edges or episodes by UUID
5. Manage the knowledge graph with tools like delete_episode, delete_entity_edge, and clear_graph

The server connects to a database for persistent storage and uses language models for certain operations. 
Each piece of information is organized by group_id, allowing you to maintain separate knowledge domains.

When adding information, provide descriptive names and detailed content to improve search quality. 
When searching, use specific queries and consider filtering by group_id for more relevant results.

For optimal performance, ensure the database is properly configured and accessible, and valid 
API keys are provided for any language model operations.
"""


# MCP server instance
mcp = FastMCP(
    'graphiti',
    instructions=GRAPHITI_MCP_INSTRUCTIONS,
)


# Initialize Graphiti client
graphiti_client: Optional[Graphiti] = None


async def initialize_graphiti(llm_client: Optional[LLMClient] = None, destroy_graph: bool = False):
    """Initialize the Graphiti client with the provided settings.

    Args:
        llm_client: Optional LLMClient instance to use for LLM operations
        destroy_graph: Optional boolean to destroy all Graphiti graphs
    """
    global graphiti_client

    # If no client is provided, create a default OpenAI client
    if not llm_client:
        if config.openai_api_key:
            llm_config = LLMConfig(api_key=config.openai_api_key)
            if config.openai_base_url:
                llm_config.base_url = config.openai_base_url
            if config.model_name:
                llm_config.model = config.model_name
            llm_client = OpenAIClient(config=llm_config)
        else:
            raise ValueError('OPENAI_API_KEY must be set when not using a custom LLM client')

    if not config.neo4j_uri or not config.neo4j_user or not config.neo4j_password:
        raise ValueError('NEO4J_URI, NEO4J_USER, and NEO4J_PASSWORD must be set')

    graphiti_client = Graphiti(
        uri=config.neo4j_uri,
        user=config.neo4j_user,
        password=config.neo4j_password,
        llm_client=llm_client,
    )

    if destroy_graph:
        logger.info('Destroying graph...')
        await clear_data(graphiti_client.driver)

    # Initialize the graph database with Graphiti's indices
    await graphiti_client.build_indices_and_constraints()
    logger.info('Graphiti client initialized successfully')


def format_fact_result(edge: EntityEdge) -> dict[str, Any]:
    """Format an entity edge into a readable result.

    Since EntityEdge is a Pydantic BaseModel, we can use its built-in serialization capabilities.

    Args:
        edge: The EntityEdge to format

    Returns:
        A dictionary representation of the edge with serialized dates and excluded embeddings
    """
    return edge.model_dump(
        mode='json',
        exclude={
            'fact_embedding',
        },
    )


# Dictionary to store queues for each group_id
# Each queue is a list of tasks to be processed sequentially
episode_queues: dict[str, asyncio.Queue] = {}
# Dictionary to track if a worker is running for each group_id
queue_workers: dict[str, bool] = {}


async def process_episode_queue(group_id: str):
    """Process episodes for a specific group_id sequentially.

    This function runs as a long-lived task that processes episodes
    from the queue one at a time.
    """
    global queue_workers

    logger.info(f'Starting episode queue worker for group_id: {group_id}')
    queue_workers[group_id] = True

    try:
        while True:
            # Get the next episode processing function from the queue
            # This will wait if the queue is empty
            process_func = await episode_queues[group_id].get()

            try:
                # Process the episode
                await process_func()
            except Exception as e:
                logger.error(f'Error processing queued episode for group_id {group_id}: {str(e)}')
            finally:
                # Mark the task as done regardless of success/failure
                episode_queues[group_id].task_done()
    except asyncio.CancelledError:
        logger.info(f'Episode queue worker for group_id {group_id} was cancelled')
    except Exception as e:
        logger.error(f'Unexpected error in queue worker for group_id {group_id}: {str(e)}')
    finally:
        queue_workers[group_id] = False
        logger.info(f'Stopped episode queue worker for group_id: {group_id}')


@mcp.tool()
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
    """Add a new track to the Graphiti knowledge graph.

    This function creates a Track entity with all the properties from the Track model,
    and optionally relates it to an Artist and/or Album if provided.

    Args:
        title (str): The title of the track
        duration_ms (str, optional): Duration in milliseconds (will be converted to int)
        explicit (str, optional): Whether the track has explicit content (will be converted to bool: "true"/"false")
        popularity (str, optional): Popularity rating 0-100 (will be converted to int)
        preview_url (str, optional): URL to a preview of the track
        isrc (str, optional): International Standard Recording Code
        lyrics (str, optional): Track lyrics
        tempo (str, optional): Tempo in BPM (will be converted to float)
        key (str, optional): Musical key
        genre (str, optional): Musical genre
        spotify_uri (str, optional): Spotify URI
        spotify_url (str, optional): Spotify URL
        artist_name (str, optional): Name of the artist to relate to this track
        album_title (str, optional): Title of the album to relate to this track
        group_id (str, optional): A unique ID for this graph. If not provided, uses the default group_id

    Returns:
        Union[SuccessResponse, ErrorResponse]: Success or error message
    """
    global graphiti_client

    if graphiti_client is None:
        return {'error': 'Graphiti client not initialized'}

    try:
        # Use the provided group_id or fall back to the default from config
        effective_group_id = group_id if group_id is not None else config.group_id

        # Cast group_id to str to satisfy type checker
        group_id_str = str(effective_group_id) if effective_group_id is not None else ''

        # We've already checked that graphiti_client is not None above
        assert graphiti_client is not None, 'graphiti_client should not be None here'

        # Use cast to help the type checker understand that graphiti_client is not None
        client = cast(Graphiti, graphiti_client)
        
        # Handle type conversions for numeric and boolean fields
        duration_ms_int = int(duration_ms) if duration_ms is not None else None
        popularity_int = int(popularity) if popularity is not None else None
        tempo_float = float(tempo) if tempo is not None else None
        explicit_bool = (explicit and explicit.lower() == 'true') if explicit is not None else None

        # Create a new track entity directly using the Track model
        track_entity = Track(
            title=title,
            duration_ms=duration_ms_int,
            explicit=explicit_bool,
            popularity=popularity_int,
            preview_url=preview_url,
            isrc=isrc,
            lyrics=lyrics,
            tempo=tempo_float,
            key=key,
            genre=genre,
            spotify_uri=spotify_uri,
            spotify_url=spotify_url
        )

        # Create a Cypher query to create the track entity with Entity and Track labels
        # This ensures it shows up in db.labels() as an Entity
        cypher_query = """
        CREATE (track:Entity:Track {
            uuid: $uuid,
            name: $title,
            title: $title,
            created_at: datetime(),
            group_id: $group_id
        })
        """
        
        # Add optional properties to the query if they exist
        params = {
            "uuid": str(uuid.uuid4()),
            "title": title,
            "group_id": group_id_str
        }
        
        # Add all the non-None properties from the track model
        track_dict = track_entity.model_dump(exclude_none=True)
        for key, value in track_dict.items():
            if key not in ["title"]:  # title is already handled
                params[key] = value
                cypher_query = cypher_query.replace("CREATE (track:Entity:Track {", 
                                                  f"CREATE (track:Entity:Track {{\n    {key}: ${key},")
        
        # Execute the query to create the track
        async with client.driver.session() as session:
            await session.run(cypher_query, params)
        
        # If artist_name is provided, create or get the artist and connect to the track
        if artist_name:
            artist_query = """
            MATCH (track:Track {uuid: $track_uuid})
            MERGE (artist:Entity:Artist {name: $artist_name, group_id: $group_id})
            CREATE (track)-[:PERFORMED_BY {
                uuid: $edge_uuid,
                created_at: datetime(),
                group_id: $group_id
            }]->(artist)
            """
            artist_params = {
                "track_uuid": params["uuid"],
                "artist_name": artist_name,
                "edge_uuid": str(uuid.uuid4()),
                "group_id": group_id_str
            }
            
            async with client.driver.session() as session:
                await session.run(artist_query, artist_params)
        
        # If album_title is provided, create or get the album and connect to the track
        if album_title:
            album_query = """
            MATCH (track:Track {uuid: $track_uuid})
            MERGE (album:Entity:Album {title: $album_title, group_id: $group_id})
            CREATE (track)-[:APPEARS_ON {
                uuid: $edge_uuid,
                created_at: datetime(),
                group_id: $group_id
            }]->(album)
            """
            album_params = {
                "track_uuid": params["uuid"],
                "album_title": album_title,
                "edge_uuid": str(uuid.uuid4()),
                "group_id": group_id_str
            }
            
            async with client.driver.session() as session:
                await session.run(album_query, album_params)
        
        # Create an episode for this track for backup/history
        track_data = {
            "track": track_dict,
            "added_directly": True
        }
        if artist_name:
            track_data["artist"] = {"name": artist_name}
        if album_title:
            track_data["album"] = {"title": album_title}
        
        # Add the track as a JSON episode for reference
        track_json = json.dumps(track_data)
        episode_name = f"Track: {title}"
        if artist_name:
            episode_name += f" by {artist_name}"
            
        await add_episode(
            name=episode_name,
            episode_body=track_json,
            source="json",
            source_description="Track data (added directly)",
            group_id=group_id_str
        )
        
        return {
            'message': f"Track '{title}' added successfully as an Entity with Track label"
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Error adding track: {error_msg}')
        return {'error': f'Error adding track: {error_msg}'}



@mcp.tool()
async def add_episode(
    name: str,
    episode_body: str,
    group_id: Optional[str] = None,
    source: str = 'text',
    source_description: str = '',
    uuid: Optional[str] = None,
) -> Union[SuccessResponse, ErrorResponse]:
    """Add an episode to the Graphiti knowledge graph. This is the primary way to add information to the graph.

    This function returns immediately and processes the episode addition in the background.
    Episodes for the same group_id are processed sequentially to avoid race conditions.

    Args:
        name (str): Name of the episode
        episode_body (str): The content of the episode. When source='json', this must be a properly escaped JSON string,
                           not a raw Python dictionary. The JSON data will be automatically processed
                           to extract entities and relationships.
        group_id (str, optional): A unique ID for this graph. If not provided, uses the default group_id from CLI
                                 or a generated one.
        source (str, optional): Source type, must be one of:
                               - 'text': For plain text content (default)
                               - 'json': For structured data
                               - 'message': For conversation-style content
        source_description (str, optional): Description of the source
        uuid (str, optional): Optional UUID for the episode

    Examples:
        # Adding plain text content
        add_episode(
            name="Company News",
            episode_body="Acme Corp announced a new product line today.",
            source="text",
            source_description="news article",
            group_id="some_arbitrary_string"
        )

        # Adding structured JSON data
        # NOTE: episode_body must be a properly escaped JSON string. Note the triple backslashes
        add_episode(
            name="Customer Profile",
            episode_body="{\\\"company\\\": {\\\"name\\\": \\\"Acme Technologies\\\"}, \\\"products\\\": [{\\\"id\\\": \\\"P001\\\", \\\"name\\\": \\\"CloudSync\\\"}, {\\\"id\\\": \\\"P002\\\", \\\"name\\\": \\\"DataMiner\\\"}]}",
            source="json",
            source_description="CRM data"
        )

        # Adding message-style content
        add_episode(
            name="Customer Conversation",
            episode_body="user: What's your return policy?\nassistant: You can return items within 30 days.",
            source="message",
            source_description="chat transcript",
            group_id="some_arbitrary_string"
        )

    Notes:
        When using source='json':
        - The JSON must be a properly escaped string, not a raw Python dictionary
        - The JSON will be automatically processed to extract entities and relationships
        - Complex nested structures are supported (arrays, nested objects, mixed data types), but keep nesting to a minimum
        - Entities will be created from appropriate JSON properties
        - Relationships between entities will be established based on the JSON structure
    """
    global graphiti_client, episode_queues, queue_workers

    if graphiti_client is None:
        return {'error': 'Graphiti client not initialized'}

    try:
        # Map string source to EpisodeType enum
        source_type = EpisodeType.text
        if source.lower() == 'message':
            source_type = EpisodeType.message
        elif source.lower() == 'json':
            source_type = EpisodeType.json

        # Use the provided group_id or fall back to the default from config
        effective_group_id = group_id if group_id is not None else config.group_id

        # Cast group_id to str to satisfy type checker
        # The Graphiti client expects a str for group_id, not Optional[str]
        group_id_str = str(effective_group_id) if effective_group_id is not None else ''

        # We've already checked that graphiti_client is not None above
        # This assert statement helps type checkers understand that graphiti_client is defined
        assert graphiti_client is not None, 'graphiti_client should not be None here'

        # Use cast to help the type checker understand that graphiti_client is not None
        client = cast(Graphiti, graphiti_client)

        # Define the episode processing function
        async def process_episode():
            try:
                logger.info(f"Processing queued episode '{name}' for group_id: {group_id_str}")
                # Use all entity types if use_custom_entities is enabled, otherwise use empty dict
                entity_types = ENTITY_TYPES if config.use_custom_entities else {}

                await client.add_episode(
                    name=name,
                    episode_body=episode_body,
                    source=source_type,
                    source_description=source_description,
                    group_id=group_id_str,  # Using the string version of group_id
                    uuid=uuid,
                    reference_time=datetime.now(timezone.utc),
                    entity_types=entity_types,
                )
                logger.info(f"Episode '{name}' added successfully")

                logger.info(f"Building communities after episode '{name}'")
                await client.build_communities()

                logger.info(f"Episode '{name}' processed successfully")
            except Exception as e:
                error_msg = str(e)
                logger.error(
                    f"Error processing episode '{name}' for group_id {group_id_str}: {error_msg}"
                )

        # Initialize queue for this group_id if it doesn't exist
        if group_id_str not in episode_queues:
            episode_queues[group_id_str] = asyncio.Queue()

        # Add the episode processing function to the queue
        await episode_queues[group_id_str].put(process_episode)

        # Start a worker for this queue if one isn't already running
        if not queue_workers.get(group_id_str, False):
            asyncio.create_task(process_episode_queue(group_id_str))

        # Return immediately with a success message
        return {
            'message': f"Episode '{name}' queued for processing (position: {episode_queues[group_id_str].qsize()})"
        }
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Error queuing episode task: {error_msg}')
        return {'error': f'Error queuing episode task: {error_msg}'}


@mcp.tool()
async def search_nodes(
    query: str,
    group_ids: Optional[list[str]] = None,
    max_nodes: int = 10,
    center_node_uuid: Optional[str] = None,
    entity: str = '',  # cursor seems to break with None
) -> Union[NodeSearchResponse, ErrorResponse]:
    """Search the Graphiti knowledge graph for relevant node summaries.
    These contain a summary of all of a node's relationships with other nodes.

    Note: entity is a single entity type to filter results (permitted: "Preference", "Procedure").

    Args:
        query: The search query
        group_ids: Optional list of group IDs to filter results
        max_nodes: Maximum number of nodes to return (default: 10)
        center_node_uuid: Optional UUID of a node to center the search around
        entity: Optional single entity type to filter results (permitted: "Preference", "Procedure")
    """
    global graphiti_client

    if graphiti_client is None:
        return ErrorResponse(error='Graphiti client not initialized')

    try:
        # Use the provided group_ids or fall back to the default from config if none provided
        effective_group_ids = (
            group_ids if group_ids is not None else [config.group_id] if config.group_id else []
        )

        # Configure the search
        if center_node_uuid is not None:
            search_config = NODE_HYBRID_SEARCH_NODE_DISTANCE.model_copy(deep=True)
        else:
            search_config = NODE_HYBRID_SEARCH_RRF.model_copy(deep=True)
        search_config.limit = max_nodes

        filters = SearchFilters()
        if entity != '':
            filters.node_labels = [entity]

        # We've already checked that graphiti_client is not None above
        assert graphiti_client is not None

        # Use cast to help the type checker understand that graphiti_client is not None
        client = cast(Graphiti, graphiti_client)

        # Perform the search using the _search method
        search_results = await client._search(
            query=query,
            config=search_config,
            group_ids=effective_group_ids,
            center_node_uuid=center_node_uuid,
            search_filter=filters,
        )

        if not search_results.nodes:
            return NodeSearchResponse(message='No relevant nodes found', nodes=[])

        # Format the node results
        formatted_nodes: list[NodeResult] = [
            {
                'uuid': node.uuid,
                'name': node.name,
                'summary': node.summary if hasattr(node, 'summary') else '',
                'labels': node.labels if hasattr(node, 'labels') else [],
                'group_id': node.group_id,
                'created_at': node.created_at.isoformat(),
                'attributes': node.attributes if hasattr(node, 'attributes') else {},
            }
            for node in search_results.nodes
        ]

        return NodeSearchResponse(message='Nodes retrieved successfully', nodes=formatted_nodes)
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Error searching nodes: {error_msg}')
        return ErrorResponse(error=f'Error searching nodes: {error_msg}')


@mcp.tool()
async def search_facts(
    query: str,
    group_ids: Optional[list[str]] = None,
    max_facts: int = 10,
    center_node_uuid: Optional[str] = None,
) -> Union[FactSearchResponse, ErrorResponse]:
    """Search the Graphiti knowledge graph for relevant facts.

    Args:
        query: The search query
        group_ids: Optional list of group IDs to filter results
        max_facts: Maximum number of facts to return (default: 10)
        center_node_uuid: Optional UUID of a node to center the search around
    """
    global graphiti_client

    if graphiti_client is None:
        return {'error': 'Graphiti client not initialized'}

    try:
        # Use the provided group_ids or fall back to the default from config if none provided
        effective_group_ids = (
            group_ids if group_ids is not None else [config.group_id] if config.group_id else []
        )

        # We've already checked that graphiti_client is not None above
        assert graphiti_client is not None

        # Use cast to help the type checker understand that graphiti_client is not None
        client = cast(Graphiti, graphiti_client)

        relevant_edges = await client.search(
            group_ids=effective_group_ids,
            query=query,
            num_results=max_facts,
            center_node_uuid=center_node_uuid,
        )

        if not relevant_edges:
            return {'message': 'No relevant facts found', 'facts': []}

        facts = [format_fact_result(edge) for edge in relevant_edges]
        return {'message': 'Facts retrieved successfully', 'facts': facts}
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Error searching facts: {error_msg}')
        return {'error': f'Error searching facts: {error_msg}'}


@mcp.tool()
async def delete_entity_edge(uuid: str) -> Union[SuccessResponse, ErrorResponse]:
    """Delete an entity edge from the Graphiti knowledge graph.

    Args:
        uuid: UUID of the entity edge to delete
    """
    global graphiti_client

    if graphiti_client is None:
        return {'error': 'Graphiti client not initialized'}

    try:
        # We've already checked that graphiti_client is not None above
        assert graphiti_client is not None

        # Use cast to help the type checker understand that graphiti_client is not None
        client = cast(Graphiti, graphiti_client)

        # Get the entity edge by UUID
        entity_edge = await EntityEdge.get_by_uuid(client.driver, uuid)
        # Delete the edge using its delete method
        await entity_edge.delete(client.driver)
        return {'message': f'Entity edge with UUID {uuid} deleted successfully'}
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Error deleting entity edge: {error_msg}')
        return {'error': f'Error deleting entity edge: {error_msg}'}


@mcp.tool()
async def delete_episode(uuid: str) -> Union[SuccessResponse, ErrorResponse]:
    """Delete an episode from the Graphiti knowledge graph.

    Args:
        uuid: UUID of the episode to delete
    """
    global graphiti_client

    if graphiti_client is None:
        return {'error': 'Graphiti client not initialized'}

    try:
        # We've already checked that graphiti_client is not None above
        assert graphiti_client is not None

        # Use cast to help the type checker understand that graphiti_client is not None
        client = cast(Graphiti, graphiti_client)

        # Get the episodic node by UUID - EpisodicNode is already imported at the top
        episodic_node = await EpisodicNode.get_by_uuid(client.driver, uuid)
        # Delete the node using its delete method
        await episodic_node.delete(client.driver)
        return {'message': f'Episode with UUID {uuid} deleted successfully'}
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Error deleting episode: {error_msg}')
        return {'error': f'Error deleting episode: {error_msg}'}


@mcp.tool()
async def get_entity_edge(uuid: str) -> Union[dict[str, Any], ErrorResponse]:
    """Get an entity edge from the Graphiti knowledge graph by its UUID.

    Args:
        uuid: UUID of the entity edge to retrieve
    """
    global graphiti_client

    if graphiti_client is None:
        return {'error': 'Graphiti client not initialized'}

    try:
        # We've already checked that graphiti_client is not None above
        assert graphiti_client is not None

        # Use cast to help the type checker understand that graphiti_client is not None
        client = cast(Graphiti, graphiti_client)

        # Get the entity edge directly using the EntityEdge class method
        entity_edge = await EntityEdge.get_by_uuid(client.driver, uuid)

        # Use the format_fact_result function to serialize the edge
        # Return the Python dict directly - MCP will handle serialization
        return format_fact_result(entity_edge)
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Error getting entity edge: {error_msg}')
        return {'error': f'Error getting entity edge: {error_msg}'}


@mcp.tool()
async def get_episodes(
    group_id: Optional[str] = None, last_n: int = 10
) -> Union[list[dict[str, Any]], EpisodeSearchResponse, ErrorResponse]:
    """Get the most recent episodes for a specific group.

    Args:
        group_id: ID of the group to retrieve episodes from. If not provided, uses the default group_id.
        last_n: Number of most recent episodes to retrieve (default: 10)
    """
    global graphiti_client

    if graphiti_client is None:
        return {'error': 'Graphiti client not initialized'}

    try:
        # Use the provided group_id or fall back to the default from config
        effective_group_id = group_id if group_id is not None else config.group_id

        if not isinstance(effective_group_id, str):
            return {'error': 'Group ID must be a string'}

        # We've already checked that graphiti_client is not None above
        assert graphiti_client is not None

        # Use cast to help the type checker understand that graphiti_client is not None
        client = cast(Graphiti, graphiti_client)

        episodes = await client.retrieve_episodes(
            group_ids=[effective_group_id], last_n=last_n, reference_time=datetime.now(timezone.utc)
        )

        if not episodes:
            return {'message': f'No episodes found for group {effective_group_id}', 'episodes': []}

        # Use Pydantic's model_dump method for EpisodicNode serialization
        formatted_episodes = [
            # Use mode='json' to handle datetime serialization
            episode.model_dump(mode='json')
            for episode in episodes
        ]

        # Return the Python list directly - MCP will handle serialization
        return formatted_episodes
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Error getting episodes: {error_msg}')
        return {'error': f'Error getting episodes: {error_msg}'}


@mcp.tool()
async def clear_graph() -> Union[SuccessResponse, ErrorResponse]:
    """Clear all data from the Graphiti knowledge graph and rebuild indices."""
    global graphiti_client

    if graphiti_client is None:
        return {'error': 'Graphiti client not initialized'}

    try:
        # We've already checked that graphiti_client is not None above
        assert graphiti_client is not None

        # Use cast to help the type checker understand that graphiti_client is not None
        client = cast(Graphiti, graphiti_client)

        # clear_data is already imported at the top
        await clear_data(client.driver)
        await client.build_indices_and_constraints()
        return {'message': 'Graph cleared successfully and indices rebuilt'}
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Error clearing graph: {error_msg}')
        return {'error': f'Error clearing graph: {error_msg}'}


@mcp.resource('http://graphiti/status')
async def get_status() -> StatusResponse:
    """Get the status of the Graphiti MCP server and Neo4j connection."""
    global graphiti_client

    if graphiti_client is None:
        return {'status': 'error', 'message': 'Graphiti client not initialized'}

    try:
        # We've already checked that graphiti_client is not None above
        assert graphiti_client is not None

        # Use cast to help the type checker understand that graphiti_client is not None
        client = cast(Graphiti, graphiti_client)

        # Test Neo4j connection
        await client.driver.verify_connectivity()
        return {'status': 'ok', 'message': 'Graphiti MCP server is running and connected to Neo4j'}
    except Exception as e:
        error_msg = str(e)
        logger.error(f'Error checking Neo4j connection: {error_msg}')
        return {
            'status': 'error',
            'message': f'Graphiti MCP server is running but Neo4j connection failed: {error_msg}',
        }


def create_llm_client(api_key: Optional[str] = None, model: Optional[str] = None) -> LLMClient:
    """Create an OpenAI LLM client.

    Args:
        api_key: API key for the OpenAI service
        model: Model name to use

    Returns:
        An instance of the OpenAI LLM client
    """
    # Create config with provided API key and model
    llm_config = LLMConfig(api_key=api_key)

    # Set model if provided
    if model:
        llm_config.model = model

    # Create and return the client
    return OpenAIClient(config=llm_config)


async def initialize_server() -> MCPConfig:
    """Initialize the Graphiti server with the specified LLM client."""
    global config

    parser = argparse.ArgumentParser(
        description='Run the Graphiti MCP server with optional LLM client'
    )
    parser.add_argument(
        '--group-id',
        help='Namespace for the graph. This is an arbitrary string used to organize related data. '
        'If not provided, a random UUID will be generated.',
    )
    parser.add_argument(
        '--transport',
        choices=['sse', 'stdio'],
        default='sse',
        help='Transport to use for communication with the client. (default: sse)',
    )
    # OpenAI is the only supported LLM client
    parser.add_argument('--model', help='Model name to use with the LLM client')
    parser.add_argument('--destroy-graph', action='store_true', help='Destroy all Graphiti graphs')
    parser.add_argument(
        '--use-custom-entities',
        action='store_true',
        help='Enable entity extraction using the predefined ENTITY_TYPES',
    )
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.environ.get('FASTMCP_PORT', 8000)),
        help='Port to run the server on (default: 8000, can be set with FASTMCP_PORT env var)',
    )

    args = parser.parse_args()

    # Set the group_id from CLI argument or generate a random one
    if args.group_id:
        config.group_id = args.group_id
        logger.info(f'Using provided group_id: {config.group_id}')
    else:
        config.group_id = f'graph_{uuid.uuid4().hex[:8]}'
        logger.info(f'Generated random group_id: {config.group_id}')

    # Set use_custom_entities flag if specified
    if args.use_custom_entities:
        config.use_custom_entities = True
        logger.info('Entity extraction enabled using predefined ENTITY_TYPES')
    else:
        logger.info('Entity extraction disabled (no custom entities will be used)')

    llm_client = None

    # Create OpenAI client if model is specified or if OPENAI_API_KEY is available
    if args.model or config.openai_api_key:
        # Override model from command line if specified

        config.model_name = args.model or DEFAULT_LLM_MODEL

        # Create the OpenAI client
        llm_client = create_llm_client(api_key=config.openai_api_key, model=config.model_name)

    # Initialize Graphiti with the specified LLM client
    await initialize_graphiti(llm_client, destroy_graph=args.destroy_graph)

    # Update the MCP server port setting if provided
    if args.port:
        mcp.settings.port = args.port
        logger.info(f'Server port set to: {args.port}')

    return MCPConfig(transport=args.transport)


async def run_mcp_server():
    """Run the MCP server in the current event loop."""
    # Initialize the server
    mcp_config = await initialize_server()

    # Log all configuration parameters
    logger.info("=== Graphiti MCP Server Configuration ===")
    logger.info(f"Group ID: {config.group_id}")
    logger.info(f"Port: {mcp.settings.port}")
    logger.info(f"Transport: {mcp_config.transport}")
    logger.info(f"Neo4j URI: {config.neo4j_uri}")
    logger.info(f"Custom entities: {'enabled' if config.use_custom_entities else 'disabled'}")
    logger.info(f"Model: {config.model_name or 'Not specified'}")
    logger.info("=========================================")

    # Run the server with stdio transport for MCP in the same event loop
    logger.info(f'Starting MCP server with transport: {mcp_config.transport}')
    if mcp_config.transport == 'stdio':
        await mcp.run_stdio_async()
    elif mcp_config.transport == 'sse':
        logger.info(
            f'Running MCP server with SSE transport on {mcp.settings.host}:{mcp.settings.port}'
        )
        await mcp.run_sse_async()


def main():
    """Main function to run the Graphiti MCP server."""
    try:
        # Run everything in a single event loop
        asyncio.run(run_mcp_server())
    except Exception as e:
        logger.error(f'Error initializing Graphiti MCP server: {str(e)}')
        raise


if __name__ == '__main__':
    main()




# MUSIC_ENTITY_TYPES: dict[str, BaseModel] = {
#     'Artist': Artist,
#     'Album': Album,
#     'Track': Track,
#     'Equipment': Equipment,
#     'Studio': Studio,
#     'Person': Person,
#     'Credit': Credit,
#     'Label': Label,
#     'Performance': Performance,
#     'Effect': Effect,
# }
# # ───────────────────────────────────────────────────────────────────────────  

# # Merge custom music entities into base registry
# ENTITY_TYPES.update(MUSIC_ENTITY_TYPES)

