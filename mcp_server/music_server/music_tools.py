import asyncio
import logging
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Union, List, Dict, cast, TypedDict

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType, EpisodicNode, EntityNode
from graphiti_core.edges import EntityEdge
from graphiti_core.search.search_config_recipes import (
    NODE_HYBRID_SEARCH_RRF,
)
from graphiti_core.search.search_filters import SearchFilters

# Import music entity models
from .models.music import (
    Artist, Album, Track, Equipment, Studio, Person, 
    Credit, Label, Performance, Effect
)

logger = logging.getLogger(__name__)

# --- Type Definitions for Tool Responses ---
class ErrorResponse(TypedDict):
    error: str

class SuccessResponse(TypedDict):
    message: str

class EntityResponse(TypedDict):
    uuid: str
    entity_type: str
    attributes: Dict[str, Any]
    created_at: str
    group_id: str

class EntitySearchResponse(TypedDict):
    message: str
    entities: List[EntityResponse]

class RelationshipResponse(TypedDict):
    uuid: str
    source_uuid: str
    target_uuid: str
    relationship_type: str
    attributes: Dict[str, Any]
    created_at: str
    group_id: str

# --- Global Instances (To be set by register_music_tools) ---
graphiti_client_instance: Optional[Graphiti] = None
mcp_instance: Optional[FastMCP] = None

# --- Helper Functions ---
def format_entity_result(node: EntityNode) -> EntityResponse:
    """Format an entity node into a standardized response."""
    entity_type = "Entity"
    if len(node.labels) > 1:
        # Get the most specific label (not 'Entity')
        entity_type = [label for label in node.labels if label != "Entity"][0]
    
    return EntityResponse(
        uuid=str(node.uuid),
        entity_type=entity_type,
        attributes=node.attributes,
        created_at=node.created_at.isoformat() if node.created_at else None,
        group_id=node.group_id
    )

def format_relationship_result(edge: EntityEdge) -> RelationshipResponse:
    """Format a relationship edge into a standardized response."""
    return RelationshipResponse(
        uuid=str(edge.uuid),
        source_uuid=str(edge.source_node_uuid),
        target_uuid=str(edge.target_node_uuid),
        relationship_type=edge.relationship_type,
        attributes=edge.attributes,
        created_at=edge.created_at.isoformat() if edge.created_at else None,
        group_id=edge.group_id
    )

# --- Entity Creation Tools ---
def register_music_tools(mcp: FastMCP, graphiti_client: Graphiti, config: Any):
    """Register all music entity tools with the FastMCP instance."""
    global graphiti_client_instance, mcp_instance
    graphiti_client_instance = graphiti_client
    mcp_instance = mcp

    if not mcp_instance:
        raise ValueError("MCP instance not set before registering music tools")

    # --- Artist Tools ---
    @mcp_instance.tool()
    async def add_artist(
        # Use basic types and defaults in signature
        artist_name: str, 
        biography: str = "",
        genres: str = "",
        active_years: str = "",
        country: str = "",
        image_url: str = "",
        influences: str = "", # Comma-separated string
        popularity: int = 0,
        followers: int = 0,
        spotify_uri: str = "",
        spotify_url: str = "",
        group_id: str = "", # Use empty string default, resolve later
    ) -> Union[EntityResponse, ErrorResponse]:
        """Add a new artist entity (using basic types in signature)."""
        logger.info(f"--- Entered add_artist (basic types) for {artist_name} ---")
        if not graphiti_client_instance:
            logger.error("Add_artist (basic types): Graphiti client not initialized")
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # # Process inputs (convert defaults back or process lists)
            # influences_list = influences.split(",") if influences else []
            # # No need to convert empty strings back to None for Optional[str/int] 
            # # in Pydantic v2 when validating dictionary data.
            
            # # Create artist data using MODEL field names
            # artist_data = {
            #     "artist_name": artist_name,
            #     "biography": biography,
            #     "genres": genres, # Model expects Optional[str]
            #     "active_years": active_years,
            #     "country": country,
            #     "image_url": image_url,
            #     "influences": influences_list, # Model expects Optional[List[str]]
            #     "popularity": popularity,
            #     "followers": followers,
            #     "spotify_uri": spotify_uri,
            #     "spotify_url": spotify_url,
            #     "schema_version": "1.0"
            # }
            # # Explicitly filter out default empty/zero values before sending
            # artist_data_filtered = {k: v for k, v in artist_data.items() if v not in ["", 0, None] and (not isinstance(v, list) or v)} # Keep non-empty lists
            
            # Create the artist node JSON body using filtered data
            # episode_body = json.dumps(artist_data_filtered)
            
            # --- Minimal Test --- 
            artist_data_minimal = {"artist_name": artist_name}
            episode_body = json.dumps(artist_data_minimal)
            # --- End Minimal Test ---

            # Resolve group_id (use input or default from config)
            effective_group_id = group_id if group_id else (config.group_id if config else "music-fallback")
            logger.info(f"Add_artist (basic types): Creating episode for {artist_name} in group {effective_group_id} with minimal body: {episode_body}")
            
            # Directly call the core add_episode method, but WITHOUT entity_types
            result = await graphiti_client_instance.add_episode(
                name=f"Artist: {artist_name}",
                episode_body=episode_body,
                source=EpisodeType.json,
                source_description=f"add_artist tool call for {artist_name}",
                reference_time=datetime.now(timezone.utc),
                group_id=effective_group_id,
                entity_types={"Artist": Artist}
            )
            
            # Extract the created artist node (might be generic Entity now)
            artist_nodes = [node for node in result.nodes if "Artist" in node.labels]
            if not artist_nodes:
                return ErrorResponse(error="Artist creation failed: no artist node found in result")
            
            # Use format_entity_result (assuming it handles the new artist_name attribute)
            return format_entity_result(artist_nodes[0])
            
        except Exception as e:
            logger.error(f"Error creating artist: {e}", exc_info=True) # Add exc_info
            return ErrorResponse(error=f"Artist creation failed: {str(e)}")

    @mcp_instance.tool()
    async def get_artist(
        uuid_str: str
    ) -> Union[EntityResponse, ErrorResponse]:
        """Get an artist by UUID."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            entity = await graphiti_client_instance.get_entity_node(uuid_str)
            if not entity or "Artist" not in entity.labels:
                return ErrorResponse(error="Artist not found or invalid entity type")
            
            return format_entity_result(entity)
            
        except Exception as e:
            logger.error(f"Error getting artist: {e}")
            return ErrorResponse(error=f"Error retrieving artist: {str(e)}")

    @mcp_instance.tool()
    async def search_artists(
        query: str,
        group_ids: Optional[List[str]] = None,
        max_results: int = 10
    ) -> Union[EntitySearchResponse, ErrorResponse]:
        """Search for artists matching the query."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Set up search filter for Artist label
            filters = SearchFilters(node_labels=["Artist"])
            
            # Execute search with the filter
            search_results = await graphiti_client_instance._search(
                query=query,
                group_ids=group_ids or ["music"],
                search_config=NODE_HYBRID_SEARCH_RRF,
                search_filters=filters,
                max_results=max_results
            )
            
            # Format results
            formatted_results = [format_entity_result(node) for node in search_results.nodes]
            
            return EntitySearchResponse(
                message=f"Found {len(formatted_results)} artists matching '{query}'",
                entities=formatted_results
            )
            
        except Exception as e:
            logger.error(f"Error searching artists: {e}")
            return ErrorResponse(error=f"Artist search failed: {str(e)}")

    @mcp_instance.tool()
    async def update_artist(
        uuid_str: str,
        name: Optional[str] = None,
        biography: Optional[str] = None,
        genres: Optional[str] = None,  # Comma-separated string
        active_years: Optional[str] = None,
        country: Optional[str] = None,
        image_url: Optional[str] = None,
        influences: Optional[str] = None,  # Comma-separated string
        popularity: Optional[int] = None,
        followers: Optional[int] = None,
        spotify_uri: Optional[str] = None,
        spotify_url: Optional[str] = None,
    ) -> Union[EntityResponse, ErrorResponse]:
        """Update an existing artist by UUID."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Get current artist
            entity = await graphiti_client_instance.get_entity_node(uuid_str)
            if not entity or "Artist" not in entity.labels:
                return ErrorResponse(error="Artist not found or invalid entity type")
            
            # Process list fields from comma-separated strings
            genres_list = genres.split(",") if genres else None
            influences_list = influences.split(",") if influences else None
            
            # Create update data with only the provided fields
            update_data = {}
            if name is not None: update_data["name"] = name
            if biography is not None: update_data["biography"] = biography
            if genres_list is not None: update_data["genres"] = genres_list
            if active_years is not None: update_data["active_years"] = active_years
            if country is not None: update_data["country"] = country
            if image_url is not None: update_data["image_url"] = image_url
            if influences_list is not None: update_data["influences"] = influences_list
            if popularity is not None: update_data["popularity"] = popularity
            if followers is not None: update_data["followers"] = followers
            if spotify_uri is not None: update_data["spotify_uri"] = spotify_uri
            if spotify_url is not None: update_data["spotify_url"] = spotify_url
            
            if not update_data:
                return ErrorResponse(error="No update data provided")
            
            # Update the entity
            updated_entity = await graphiti_client_instance.update_entity_node(
                uuid_str=uuid_str,
                attributes=update_data
            )
            
            return format_entity_result(updated_entity)
            
        except Exception as e:
            logger.error(f"Error updating artist: {e}")
            return ErrorResponse(error=f"Artist update failed: {str(e)}")

    @mcp_instance.tool()
    async def delete_artist(
        uuid_str: str
    ) -> Union[SuccessResponse, ErrorResponse]:
        """Delete an artist by UUID."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify it's an artist
            entity = await graphiti_client_instance.get_entity_node(uuid_str)
            if not entity or "Artist" not in entity.labels:
                return ErrorResponse(error="Artist not found or invalid entity type")
            
            # Delete the entity
            await graphiti_client_instance.delete_entity_node(uuid_str)
            
            return SuccessResponse(message=f"Artist {entity.attributes.get('name', 'unknown')} deleted successfully")
            
        except Exception as e:
            logger.error(f"Error deleting artist: {e}")
            return ErrorResponse(error=f"Artist deletion failed: {str(e)}")

    # --- Album Tools ---
    @mcp_instance.tool()
    async def add_album(
        # Use basic types and defaults in signature
        album_title: str,
        release_date: str = "",
        album_type: str = "",
        total_tracks: int = 0,
        catalog_number: str = "",
        images: str = "",  # JSON string of image objects
        release_date_precision: str = "",
        spotify_uri: str = "",
        spotify_url: str = "",
        genres: str = "",  # Comma-separated string
        description: str = "",
        producer: str = "",
        length_minutes: int = 0,
        group_id: str = "", # Use empty string default, resolve later
    ) -> Union[EntityResponse, ErrorResponse]:
        """Add a new album entity (using basic types in signature)."""
        logger.info(f"--- Entered add_album (basic types) for {album_title} ---")
        if not graphiti_client_instance:
            logger.error("Add_album (basic types): Graphiti client not initialized")
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Process inputs (convert defaults back or process lists/json)
            genres_list = genres.split(",") if genres else []
            images_list = json.loads(images) if images else [] # Expects JSON string input
            
            # Create album data using MODEL field names
            album_data = {
                "album_title": album_title,
                "release_date": release_date,
                "album_type": album_type,
                "total_tracks": total_tracks,
                "catalog_number": catalog_number,
                "images": images_list, # Model expects Optional[List[Dict[str, str]]]
                "release_date_precision": release_date_precision,
                "spotify_uri": spotify_uri,
                "spotify_url": spotify_url,
                "genres": genres_list, # Model expects Optional[List[str]]
                "description": description,
                "producer": producer,
                "length_minutes": length_minutes,
                "schema_version": "1.0"
            }
            # Explicitly filter out default empty/zero values before sending
            album_data_filtered = {k: v for k, v in album_data.items() if v not in ["", 0, None] and (not isinstance(v, list) or v)} # Keep non-empty lists
            
            # Create the album node JSON body using filtered data
            episode_body = json.dumps(album_data_filtered)
            # Resolve group_id
            effective_group_id = group_id if group_id else (config.group_id if config else "music-fallback")
            logger.info(f"Add_album (basic types): Creating episode for {album_title} in group {effective_group_id}")
            
            # Directly call the core add_episode method, but WITHOUT entity_types
            result = await graphiti_client_instance.add_episode(
                name=f"Album: {album_title}",
                episode_body=episode_body,
                source=EpisodeType.json,
                source_description=f"add_album tool call for {album_title}",
                reference_time=datetime.now(timezone.utc),
                group_id=effective_group_id,
                entity_types={"Album": Album}
            )
            
            # Extract the created album node (might be generic Entity now)
            album_nodes = [node for node in result.nodes if "Album" in node.labels]
            if not album_nodes:
                return ErrorResponse(error="Album creation failed: no album node found in result")
            
            # Use format_entity_result (assuming it handles the new album_title attribute)
            return format_entity_result(album_nodes[0])
            
        except Exception as e:
            logger.error(f"Error creating album: {e}", exc_info=True) # Add exc_info
            return ErrorResponse(error=f"Album creation failed: {str(e)}") 