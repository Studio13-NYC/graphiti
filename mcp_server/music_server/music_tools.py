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
from neontology import BaseNode, GraphConnection
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
# graphiti_client_instance: Optional[Graphiti] = None # No longer needed directly in this file's tools
mcp_instance: Optional[FastMCP] = None

# --- Helper Functions ---
# Moved helper to module level
# TODO: Potentially move this to a shared utility module
def format_neontology_node(node: BaseNode) -> EntityResponse:
    # Assumes node has been successfully created/merged/retrieved
    attributes = node.model_dump(exclude={'id'}) # Exclude internal ID if present
    # Neontology doesn't explicitly store created_at on BaseNode by default
    # We might need to add it to our models or fetch it via Cypher if needed
    return EntityResponse(
        uuid=str(getattr(node, node.__primaryproperty__, 'N/A')), # Use primary property as a pseudo-UUID for response
        entity_type=node.__primarylabel__, # Get label directly
        attributes=attributes,
        created_at=datetime.now(timezone.utc).isoformat(), # Placeholder - Actual creation time not stored by default
        group_id=getattr(node, 'group_id', '') # Assuming group_id might be added later or handled differently
    )

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
def register_music_tools(mcp: FastMCP, config: Any): # Removed graphiti_client parameter
    """Register all music entity tools with the FastMCP instance."""
    # Keep graphiti_client for now, might be needed for other tools or search
    # global graphiti_client_instance, mcp_instance 
    global mcp_instance # Only set mcp_instance
    # graphiti_client_instance = graphiti_client # Removed assignment
    mcp_instance = mcp

    if not mcp_instance:
        raise ValueError("MCP instance not set before registering music tools")

    # Helper to format Neontology Node to EntityResponse
    # MOVED TO MODULE LEVEL
    # def format_neontology_node(node: BaseNode) -> EntityResponse:
    #     ...

    # --- Artist Tools ---
    @mcp_instance.tool()
    async def add_artist(
        # Signature remains the same for LLM compatibility
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
        group_id: str = "", # Group ID handling needs clarification with neontology
    ) -> Union[EntityResponse, ErrorResponse]:
        """Add a new artist entity using Neontology for backend persistence."""
        logger.info(f"--- Entered add_artist (Neontology) for {artist_name} ---")
        
        try:
            # Process inputs (like splitting lists)
            # NOTE: Neontology v2 handles Optional fields gracefully during instantiation.
            # No need to filter defaults like "", 0 before creating the instance.
            influences_list = influences.split(",") if influences else None # Use None if empty for Optional[List]
            
            # Instantiate the Neontology Artist model
            # Note: group_id is not part of the core BaseNode. Needs consideration.
            # If group_id is critical, it should be added as an Optional[str] field 
            # to the Artist model itself in models/music.py.
            artist_instance = Artist(
                artist_name=artist_name,
                biography=biography if biography else None,
                genres=genres if genres else None, # Model expects Optional[str]
                active_years=active_years if active_years else None,
                country=country if country else None,
                image_url=image_url if image_url else None,
                influences=influences_list,
                popularity=popularity if popularity != 0 else None,
                followers=followers if followers != 0 else None,
                spotify_uri=spotify_uri if spotify_uri else None,
                spotify_url=spotify_url if spotify_url else None,
                # schema_version="1.0" # Assuming this is added to Artist model
            )

            # Persist using Neontology's merge (upsert based on primary property)
            # NOTE: Neontology methods are synchronous by default.
            # Running in default executor to avoid blocking the async event loop.
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, artist_instance.merge)
            # TODO: Confirm if neontology has async methods or if this sync approach is acceptable.

            logger.info(f"Add_artist (Neontology): Merged artist {artist_name}")

            # Format and return the response based on the instance data
            # The instance *should* reflect the merged state, but neontology docs
            # are unclear if merge() updates the instance in place.
            # We might need a find_one() call after merge if not.
            # Using a placeholder formatter for now.
            # TODO: Implement robust formatting/retrieval after merge/create.
            return format_neontology_node(artist_instance)
            
        except Exception as e:
            logger.error(f"Error creating artist with Neontology: {e}", exc_info=True)
            return ErrorResponse(error=f"Artist creation failed: {str(e)}")

    @mcp_instance.tool()
    async def get_artist(
        uuid_str: str # Assuming this is the artist_name (primary property)
    ) -> Union[EntityResponse, ErrorResponse]:
        """Get an artist by its primary property (artist_name) using Neontology."""
        logger.info(f"--- Entered get_artist (Neontology) for {uuid_str} ---")
        # No need for graphiti_client_instance here
        # if not graphiti_client_instance:
        #     return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Find the artist node using Neontology's evaluate_query
            from neontology import GraphConnection
            gc = GraphConnection()
            cypher_query = "MATCH (a:Artist {artist_name: $name_param}) RETURN a LIMIT 1"
            params = {"name_param": uuid_str}

            # Running in executor as neontology methods are sync
            loop = asyncio.get_running_loop()
            query_result = await loop.run_in_executor(
                None, 
                # Pass query as positional arg, params as second arg
                lambda: gc.evaluate_query(cypher_query, params)
            )
            
            # Check if any nodes were returned
            if not query_result or not query_result.nodes:
                logger.warning(f"Get_artist (Neontology): Artist not found for name: {uuid_str}")
                return ErrorResponse(error=f"Artist with name '{uuid_str}' not found")
            
            # Get the first node (should be an Artist instance)
            artist_instance = query_result.nodes[0]

            logger.info(f"Get_artist (Neontology): Found artist {artist_instance.artist_name}")
            # Use the existing helper to format the response
            return format_neontology_node(artist_instance)
            
        except Exception as e:
            logger.error(f"Error getting artist with Neontology: {e}", exc_info=True)
            return ErrorResponse(error=f"Error retrieving artist: {str(e)}")

    @mcp_instance.tool()
    async def search_artists(
        query: str,
        group_ids: str = "", # Non-optional string; Group ID handling TBD with neontology
        max_results: int = 10
    ) -> Union[EntitySearchResponse, ErrorResponse]:
        """Search for artists matching the query using Neontology (basic name search)."""
        logger.info(f"--- Entered search_artists (Neontology) for query '{query}' ---")
        # if not graphiti_client_instance:
        #     return ErrorResponse(error="Graphiti client not initialized")

        try:
            # Basic search: Find nodes where the primary property contains the query string (case-insensitive)
            # NOTE: This requires custom Cypher as neontology's find is exact match.
            # Using GraphConnection().evaluate_query
            # Neontology connection should be initialized already
            gc = GraphConnection()

            # Split group_ids string if provided
            group_ids_list = group_ids.split(',') if group_ids else None

            # We need to adapt the query based on how group_ids are handled.
            # Assuming group_id is NOT yet a standard node property.
            # If group_id *is* added to the Artist model, adjust the query.
            # TODO: Implement group_id filtering in Cypher if needed and possible
            cypher_query = (
                f"MATCH (a:Artist) "
                f"WHERE toLower(a.artist_name) CONTAINS toLower($query_param) "
                # Add group_id filtering here if implemented, e.g.:
                # f"AND a.group_id IN $group_ids_param " # If group_id is a property
                f"RETURN a "
                f"LIMIT $limit_param"
            )
            params = {
                "query_param": query,
                "limit_param": max_results
                # Add group_ids_param if filtering is implemented:
                # "group_ids_param": group_ids_list if group_ids_list else [] 
            }

            # Running in executor as neontology methods are sync
            loop = asyncio.get_running_loop()
            query_result = await loop.run_in_executor(
                None,
                # Pass query as positional arg, params as second arg
                lambda: gc.evaluate_query(cypher_query, params)
            )

            if not query_result or not query_result.nodes:
                logger.info(f"Search_artists (Neontology): No artists found matching '{query}'")
                # Return empty list, not an error
                return EntitySearchResponse(message=f"No artists found matching '{query}'", entities=[])

            # Format results
            # Neontology's evaluate_query returns a results object with .nodes
            found_nodes = query_result.nodes # These should be Artist instances
            formatted_entities = [format_neontology_node(node) for node in found_nodes]
            logger.info(f"Search_artists (Neontology): Found {len(formatted_entities)} artists matching '{query}'")
            return EntitySearchResponse(
                message=f"Found {len(formatted_entities)} artists matching '{query}'", 
                entities=formatted_entities
            )

        except Exception as e:
            logger.error(f"Error searching artists with Neontology: {e}", exc_info=True)
            return ErrorResponse(error=f"Error searching artists: {str(e)}")

    @mcp_instance.tool()
    async def update_artist(
        uuid_str: str, # Assuming this is the artist_name (primary property)
        # Change Optional types to basic types with defaults for MCP compatibility
        artist_name: str = "", # Allow updating the primary property
        biography: str = "",
        genres: str = "",
        active_years: str = "",
        country: str = "",
        image_url: str = "",
        influences: str = "",  # Comma-separated string input
        popularity: int = 0,
        followers: int = 0,
        spotify_uri: str = "",
        spotify_url: str = "",
        # Add other Artist fields if needed for updates
    ) -> Union[EntityResponse, ErrorResponse]:
        """Update an existing artist by its primary property (artist_name) using Neontology."""
        logger.info(f"--- Entered update_artist (Neontology) for {uuid_str} ---")
        
        try:
            # Find the existing artist node using evaluate_query (like get_artist)
            from neontology import GraphConnection
            gc = GraphConnection()
            primary_prop = Artist.__primaryproperty__
            cypher_query = f"MATCH (a:Artist {{{primary_prop}: $uuid_param}}) RETURN a LIMIT 1"
            params = {"uuid_param": uuid_str}
            
            loop = asyncio.get_running_loop()
            query_result = await loop.run_in_executor(
                None, 
                lambda: gc.evaluate_query(cypher_query, params)
            )

            # Check if artist found
            if not query_result or not query_result.nodes:
                logger.warning(f"Update_artist (Neontology): Artist not found for {primary_prop}: {uuid_str}")
                return ErrorResponse(error=f"Artist with {primary_prop} '{uuid_str}' not found for update")
            
            artist_instance = query_result.nodes[0]
            logger.info(f"Update_artist (Neontology): Found artist {uuid_str} to update.")

            # Process inputs and create update dictionary
            # Handle defaults provided in signature: only update if value is not the default
            update_data = {}
            if artist_name != "": update_data['artist_name'] = artist_name
            if biography != "": update_data['biography'] = biography
            if genres != "": update_data['genres'] = genres
            if active_years != "": update_data['active_years'] = active_years
            if country != "": update_data['country'] = country
            if image_url != "": update_data['image_url'] = image_url
            if influences != "":
                # Split comma-separated string into list for the model
                update_data['influences'] = [inf.strip() for inf in influences.split(',') if inf.strip()]
            # If influences is empty string, explicitly set to None or empty list based on model
            # If the model field is Optional[List[str]], setting to empty list might be safer if None isn't desired
            # Let's assume we want to clear it if an empty string is passed.
            elif influences == "" and hasattr(artist_instance, 'influences'): # Check if attribute exists before clearing
                 # Decide whether to set to None or [] based on model definition (assuming List)
                 update_data['influences'] = [] # Or None if model allows Optional[List] and None is desired
            if popularity != 0: update_data['popularity'] = popularity
            if followers != 0: update_data['followers'] = followers
            if spotify_uri != "": update_data['spotify_uri'] = spotify_uri
            if spotify_url != "": update_data['spotify_url'] = spotify_url

            if not update_data:
                # Return the existing node if no updates were provided
                logger.warning(f"Update_artist (Neontology): No update data provided for {uuid_str}")
                return format_neontology_node(artist_instance)

            # Update the instance attributes retrieved from the query
            logger.info(f"Update_artist (Neontology): Applying updates: {update_data}")
            any_updates_applied = False
            for key, value in update_data.items():
                if hasattr(artist_instance, key):
                    setattr(artist_instance, key, value)
                    any_updates_applied = True
                else:
                    logger.warning(f"Update_artist (Neontology): Attribute '{key}' not found on Artist instance, skipping update.")
            
            # Only merge if actual updates were applied
            if any_updates_applied:
                # Persist the changes using Neontology's merge method (upsert)
                await loop.run_in_executor(None, artist_instance.merge)
                logger.info(f"Update_artist (Neontology): Merged updated artist {uuid_str}")
            else:
                logger.info(f"Update_artist (Neontology): No relevant updates applied for {uuid_str}, merge skipped.")

            # Return the updated artist info (merge should update the instance)
            return format_neontology_node(artist_instance)
            
        except Exception as e:
            logger.error(f"Error updating artist with Neontology: {e}", exc_info=True)
            return ErrorResponse(error=f"Artist update failed: {str(e)}")

    @mcp_instance.tool()
    async def delete_artist(
        uuid_str: str # Assuming this is the artist_name (primary property)
    ) -> Union[SuccessResponse, ErrorResponse]:
        """Delete an artist by its primary property (artist_name) using Neontology via Cypher."""
        logger.info(f"--- Entered delete_artist (Neontology/Cypher - No Check) for {uuid_str} ---")
        
        try:
            # Use a direct Cypher DETACH DELETE query
            from neontology import GraphConnection
            gc = GraphConnection()
            primary_prop = Artist.__primaryproperty__
            # DETACH DELETE query - works even if node doesn't exist
            delete_query = f"MATCH (a:Artist {{{primary_prop}: $uuid_param}}) DETACH DELETE a"
            params = {"uuid_param": uuid_str}

            loop = asyncio.get_running_loop()

            # Execute the delete query directly
            await loop.run_in_executor(
                None, 
                lambda: gc.evaluate_query(delete_query, params)
            )
            # Note: evaluate_query might not return useful info for DELETE, just executes it.

            logger.info(f"Delete_artist (Neontology/Cypher - No Check): Executed DETACH DELETE for artist {uuid_str}")
            
            # Assume success, as DETACH DELETE doesn't error if node not found
            return SuccessResponse(message=f"Attempted deletion for Artist '{uuid_str}'. Check logs if issues persist.")
            
        except Exception as e:
            logger.error(f"Error deleting artist with Neontology/Cypher: {e}", exc_info=True)
            return ErrorResponse(error=f"Artist deletion failed: {str(e)}")

    # --- Album Tools ---
    @mcp_instance.tool()
    async def add_album(
        album_title: str,
        release_date: str = "",
        album_type: str = "",
        total_tracks: int = 0,
        catalog_number: str = "",
        images: str = "",  # JSON string of image objects { "url": "...", "height": H, "width": W }
        release_date_precision: str = "",
        spotify_uri: str = "",
        spotify_url: str = "",
        genres: str = "",  # Comma-separated string
        description: str = "",
        producer: str = "",
        length_minutes: int = 0,
        group_id: str = "", # Use empty string default, resolve later
    ) -> Union[EntityResponse, ErrorResponse]:
        """Add a new album entity using Neontology for backend persistence."""
        logger.info(f"--- Entered add_album (Neontology) for {album_title} ---")

        try:
            # Parse genres string
            genre_list = [g.strip() for g in genres.split(',') if g.strip()] if genres else None
            
            # Re-introduce images parsing from string input
            images_list = None
            if images:
                try:
                    parsed_images = json.loads(images)
                    # Basic validation: ensure it's a list of dicts
                    if isinstance(parsed_images, list) and all(isinstance(item, dict) for item in parsed_images):
                        images_list = parsed_images
                    else:
                        logger.warning(f"Add_album: Invalid format for images JSON: {images}")
                        # Proceeding without images for now.
                except json.JSONDecodeError as json_e:
                    logger.warning(f"Add_album: Could not parse images JSON '{images}': {json_e}")
                    # Proceeding without images

            # Create Album instance
            album_instance = Album(
                album_title=album_title,
                release_date=release_date if release_date else None,
                album_type=album_type if album_type else None,
                total_tracks=total_tracks if total_tracks != 0 else None,
                catalog_number=catalog_number if catalog_number else None,
                images=images_list, # Model expects Optional[List[Dict[str, str/Any]]]
                release_date_precision=release_date_precision if release_date_precision else None,
                spotify_uri=spotify_uri if spotify_uri else None,
                spotify_url=spotify_url if spotify_url else None,
                genres=genre_list, # Model expects Optional[List[str]]
                description=description if description else None,
                producer=producer if producer else None,
                length_minutes=length_minutes if length_minutes != 0 else None,
                # Add other fields like rating, schema_version if needed/available
                schema_version="1.0"
            )

            # Persist using Neontology merge
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, album_instance.merge)

            logger.info(f"Add_album (Neontology): Merged album {album_title}")

            # Format and return response
            return format_neontology_node(album_instance)

        except Exception as e:
            logger.error(f"Error creating album '{album_title}' with Neontology: {e}", exc_info=True)
            return ErrorResponse(error=f"Album creation failed: {str(e)}")

    @mcp_instance.tool()
    async def get_album(
        uuid_str: str # Assuming this is the album_title (primary property)
    ) -> Union[EntityResponse, ErrorResponse]:
        """Get an album by its primary property (album_title) using Neontology."""
        logger.info(f"--- Entered get_album (Neontology) for {uuid_str} ---")
        
        try:
            # Find the album node using Neontology's find_one method
            loop = asyncio.get_running_loop()
            album_instance = await loop.run_in_executor(
                None, 
                lambda: Album.find_one(album_title=uuid_str)
            )
            
            if not album_instance:
                logger.warning(f"Get_album (Neontology): Album not found for title: {uuid_str}")
                return ErrorResponse(error=f"Album with title '{uuid_str}' not found")
            
            logger.info(f"Get_album (Neontology): Found album {album_instance.album_title}")
            # Use the helper to format the response
            return format_neontology_node(album_instance)
            
        except Exception as e:
            logger.error(f"Error getting album '{uuid_str}' with Neontology: {e}", exc_info=True)
            return ErrorResponse(error=f"Error retrieving album: {str(e)}")

  
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