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

# Import from other modules
from .music_tools import (
    ErrorResponse, SuccessResponse, EntityResponse, 
    RelationshipResponse, format_relationship_result
)

logger = logging.getLogger(__name__)

# --- Global Instances ---
graphiti_client_instance: Optional[Graphiti] = None
mcp_instance: Optional[FastMCP] = None

# --- Relationship Tools Registration ---
def register_relationship_tools(mcp: FastMCP, graphiti_client: Graphiti):
    """Register relationship management tools with the FastMCP instance."""
    global graphiti_client_instance, mcp_instance
    graphiti_client_instance = graphiti_client
    mcp_instance = mcp

    if not mcp_instance:
        raise ValueError("MCP instance not set before registering relationship tools")

    # --- Generic Relationship Management ---
    @mcp_instance.tool()
    async def create_relationship(
        source_uuid: str,
        target_uuid: str,
        relationship_type: str,
        attributes_json: Optional[str] = None,  # JSON string of attributes
        group_id: Optional[str] = None,
    ) -> Union[RelationshipResponse, ErrorResponse]:
        """Create a generic relationship between two entities with any relationship type."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify entities exist
            source = await graphiti_client_instance.get_entity_node(source_uuid)
            target = await graphiti_client_instance.get_entity_node(target_uuid)
            
            if not source:
                return ErrorResponse(error=f"Source entity with UUID {source_uuid} not found")
            
            if not target:
                return ErrorResponse(error=f"Target entity with UUID {target_uuid} not found")
            
            # Parse attributes if provided
            attributes = {}
            if attributes_json:
                try:
                    attributes = json.loads(attributes_json)
                except json.JSONDecodeError:
                    return ErrorResponse(error="Invalid JSON in attributes_json parameter")
            
            effective_group_id = group_id or "music"
            
            # Create the relationship
            edge = await graphiti_client_instance.add_entity_edge(
                source_node_uuid=source_uuid,
                target_node_uuid=target_uuid,
                relationship_type=relationship_type.upper(),  # Convention: uppercase relationship types
                attributes=attributes,
                group_id=effective_group_id
            )
            
            return format_relationship_result(edge)
            
        except Exception as e:
            logger.error(f"Error creating relationship: {e}")
            return ErrorResponse(error=f"Failed to create relationship: {str(e)}")

    @mcp_instance.tool()
    async def update_relationship(
        relationship_uuid: str,
        attributes_json: str,  # JSON string of attributes to update
    ) -> Union[RelationshipResponse, ErrorResponse]:
        """Update the attributes of an existing relationship."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify relationship exists
            edge = await graphiti_client_instance.get_entity_edge(relationship_uuid)
            if not edge:
                return ErrorResponse(error=f"Relationship with UUID {relationship_uuid} not found")
            
            # Parse attributes
            try:
                attributes = json.loads(attributes_json)
            except json.JSONDecodeError:
                return ErrorResponse(error="Invalid JSON in attributes_json parameter")
            
            # Update the relationship
            updated_edge = await graphiti_client_instance.update_entity_edge(
                uuid_str=relationship_uuid,
                attributes=attributes
            )
            
            return format_relationship_result(updated_edge)
            
        except Exception as e:
            logger.error(f"Error updating relationship: {e}")
            return ErrorResponse(error=f"Failed to update relationship: {str(e)}")

    @mcp_instance.tool()
    async def delete_relationship(
        relationship_uuid: str
    ) -> Union[SuccessResponse, ErrorResponse]:
        """Delete a relationship by UUID."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify relationship exists
            edge = await graphiti_client_instance.get_entity_edge(relationship_uuid)
            if not edge:
                return ErrorResponse(error=f"Relationship with UUID {relationship_uuid} not found")
            
            # Delete the relationship
            await graphiti_client_instance.delete_entity_edge(relationship_uuid)
            
            return SuccessResponse(message=f"Relationship {edge.relationship_type} deleted successfully")
            
        except Exception as e:
            logger.error(f"Error deleting relationship: {e}")
            return ErrorResponse(error=f"Failed to delete relationship: {str(e)}")

    @mcp_instance.tool()
    async def get_relationships(
        entity_uuid: str,
        relationship_type: Optional[str] = None,
        direction: str = "both",  # "incoming", "outgoing", or "both"
        group_ids: Optional[List[str]] = None,
    ) -> Union[Dict[str, Any], ErrorResponse]:
        """Get all relationships for an entity, optionally filtered by type and direction."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify entity exists
            entity = await graphiti_client_instance.get_entity_node(entity_uuid)
            if not entity:
                return ErrorResponse(error=f"Entity with UUID {entity_uuid} not found")
            
            effective_group_ids = group_ids or ["music"]
            
            # Validate direction
            if direction not in ["incoming", "outgoing", "both"]:
                return ErrorResponse(error="Direction must be 'incoming', 'outgoing', or 'both'")
            
            # Get relationships
            edges = await graphiti_client_instance.get_entity_edges_by_node(
                node_uuid=entity_uuid,
                relationship_type=relationship_type,
                group_ids=effective_group_ids,
                direction=direction
            )
            
            # Format results
            formatted_edges = [format_relationship_result(edge) for edge in edges]
            
            # Get entity name/title for better message
            entity_name = entity.attributes.get("name", entity.attributes.get("title", "entity"))
            
            return {
                "message": f"Found {len(formatted_edges)} relationships for {entity_name}",
                "relationships": formatted_edges
            }
            
        except Exception as e:
            logger.error(f"Error getting relationships: {e}")
            return ErrorResponse(error=f"Failed to get relationships: {str(e)}")

    # --- Music-Specific Relationship Tools ---
    
    @mcp_instance.tool()
    async def record_track_at_studio(
        track_uuid: str,
        studio_uuid: str,
        recording_date: Optional[str] = None,
        engineers: Optional[str] = None,  # Comma-separated string of engineer names
        equipment_used: Optional[str] = None,  # Comma-separated string of equipment names
        group_id: Optional[str] = None,
    ) -> Union[RelationshipResponse, ErrorResponse]:
        """Create a relationship indicating a track was recorded at a specific studio."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify entities exist and are of correct type
            track = await graphiti_client_instance.get_entity_node(track_uuid)
            studio = await graphiti_client_instance.get_entity_node(studio_uuid)
            
            if not track or "Track" not in track.labels:
                return ErrorResponse(error="Track not found or invalid entity type")
            
            if not studio or "Studio" not in studio.labels:
                return ErrorResponse(error="Studio not found or invalid entity type")
            
            # Process list fields
            engineers_list = engineers.split(",") if engineers else None
            equipment_list = equipment_used.split(",") if equipment_used else None
            
            # Create relationship attributes
            attributes = {}
            if recording_date:
                attributes["recording_date"] = recording_date
            if engineers_list:
                attributes["engineers"] = engineers_list
            if equipment_list:
                attributes["equipment_used"] = equipment_list
            
            effective_group_id = group_id or "music"
            
            # Create the relationship
            edge = await graphiti_client_instance.add_entity_edge(
                source_node_uuid=track_uuid,
                target_node_uuid=studio_uuid,
                relationship_type="RECORDED_AT",
                attributes=attributes,
                group_id=effective_group_id
            )
            
            return format_relationship_result(edge)
            
        except Exception as e:
            logger.error(f"Error creating track-studio relationship: {e}")
            return ErrorResponse(error=f"Failed to record track at studio: {str(e)}")

    @mcp_instance.tool()
    async def add_equipment_to_track(
        track_uuid: str,
        equipment_uuid: str,
        context: Optional[str] = None,
        settings: Optional[str] = None,  # JSON string of equipment settings
        performer: Optional[str] = None,  # Who used the equipment
        group_id: Optional[str] = None,
    ) -> Union[RelationshipResponse, ErrorResponse]:
        """Create a relationship indicating equipment was used on a track."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify entities exist and are of correct type
            track = await graphiti_client_instance.get_entity_node(track_uuid)
            equipment = await graphiti_client_instance.get_entity_node(equipment_uuid)
            
            if not track or "Track" not in track.labels:
                return ErrorResponse(error="Track not found or invalid entity type")
            
            if not equipment or "Equipment" not in equipment.labels:
                return ErrorResponse(error="Equipment not found or invalid entity type")
            
            # Parse settings if provided
            settings_dict = {}
            if settings:
                try:
                    settings_dict = json.loads(settings)
                except json.JSONDecodeError:
                    return ErrorResponse(error="Invalid JSON in settings parameter")
            
            # Create relationship attributes
            attributes = {}
            if context:
                attributes["context"] = context
            if settings_dict:
                attributes["settings"] = settings_dict
            if performer:
                attributes["performer"] = performer
            
            effective_group_id = group_id or "music"
            
            # Create the relationship
            edge = await graphiti_client_instance.add_entity_edge(
                source_node_uuid=track_uuid,
                target_node_uuid=equipment_uuid,
                relationship_type="USED_EQUIPMENT",
                attributes=attributes,
                group_id=effective_group_id
            )
            
            return format_relationship_result(edge)
            
        except Exception as e:
            logger.error(f"Error creating track-equipment relationship: {e}")
            return ErrorResponse(error=f"Failed to add equipment to track: {str(e)}")

    @mcp_instance.tool()
    async def assign_person_to_track(
        person_uuid: str,
        track_uuid: str,
        role: str,  # e.g., "producer", "engineer", "mixer"
        contribution_details: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> Union[RelationshipResponse, ErrorResponse]:
        """Create a relationship between a production person and a track."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify entities exist and are of correct type
            person = await graphiti_client_instance.get_entity_node(person_uuid)
            track = await graphiti_client_instance.get_entity_node(track_uuid)
            
            if not person or "Person" not in person.labels:
                return ErrorResponse(error="Person not found or invalid entity type")
            
            if not track or "Track" not in track.labels:
                return ErrorResponse(error="Track not found or invalid entity type")
            
            # Create relationship attributes
            attributes = {"role": role}
            if contribution_details:
                attributes["contribution_details"] = contribution_details
            
            effective_group_id = group_id or "music"
            
            # Create the relationship
            edge = await graphiti_client_instance.add_entity_edge(
                source_node_uuid=person_uuid,
                target_node_uuid=track_uuid,
                relationship_type="CONTRIBUTED_TO",
                attributes=attributes,
                group_id=effective_group_id
            )
            
            return format_relationship_result(edge)
            
        except Exception as e:
            logger.error(f"Error creating person-track relationship: {e}")
            return ErrorResponse(error=f"Failed to assign person to track: {str(e)}")

    @mcp_instance.tool()
    async def link_artist_album(
        artist_uuid: str,
        album_uuid: str,
        role: Optional[str] = "primary_artist",  # primary_artist, featured, compilation, etc.
        group_id: Optional[str] = None,
    ) -> Union[RelationshipResponse, ErrorResponse]:
        """Create a relationship between an artist and an album."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify entities exist and are of correct type
            artist = await graphiti_client_instance.get_entity_node(artist_uuid)
            album = await graphiti_client_instance.get_entity_node(album_uuid)
            
            if not artist or "Artist" not in artist.labels:
                return ErrorResponse(error="Artist not found or invalid entity type")
            
            if not album or "Album" not in album.labels:
                return ErrorResponse(error="Album not found or invalid entity type")
            
            # Create relationship attributes
            attributes = {"role": role}
            
            effective_group_id = group_id or "music"
            
            # Create the relationship
            edge = await graphiti_client_instance.add_entity_edge(
                source_node_uuid=artist_uuid,
                target_node_uuid=album_uuid,
                relationship_type="RELEASED_ALBUM",
                attributes=attributes,
                group_id=effective_group_id
            )
            
            return format_relationship_result(edge)
            
        except Exception as e:
            logger.error(f"Error creating artist-album relationship: {e}")
            return ErrorResponse(error=f"Failed to link artist to album: {str(e)}")

    @mcp_instance.tool()
    async def add_effect_to_track(
        track_uuid: str,
        effect_uuid: str,
        context: Optional[str] = None,
        settings: Optional[str] = None,  # JSON string of effect settings
        applied_by: Optional[str] = None,  # Who applied the effect
        group_id: Optional[str] = None,
    ) -> Union[RelationshipResponse, ErrorResponse]:
        """Create a relationship indicating an effect was used on a track."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify entities exist and are of correct type
            track = await graphiti_client_instance.get_entity_node(track_uuid)
            effect = await graphiti_client_instance.get_entity_node(effect_uuid)
            
            if not track or "Track" not in track.labels:
                return ErrorResponse(error="Track not found or invalid entity type")
            
            if not effect or "Effect" not in effect.labels:
                return ErrorResponse(error="Effect not found or invalid entity type")
            
            # Parse settings if provided
            settings_dict = {}
            if settings:
                try:
                    settings_dict = json.loads(settings)
                except json.JSONDecodeError:
                    return ErrorResponse(error="Invalid JSON in settings parameter")
            
            # Create relationship attributes
            attributes = {}
            if context:
                attributes["context"] = context
            if settings_dict:
                attributes["settings"] = settings_dict
            if applied_by:
                attributes["applied_by"] = applied_by
            
            effective_group_id = group_id or "music"
            
            # Create the relationship
            edge = await graphiti_client_instance.add_entity_edge(
                source_node_uuid=track_uuid,
                target_node_uuid=effect_uuid,
                relationship_type="USED_EFFECT",
                attributes=attributes,
                group_id=effective_group_id
            )
            
            return format_relationship_result(edge)
            
        except Exception as e:
            logger.error(f"Error creating track-effect relationship: {e}")
            return ErrorResponse(error=f"Failed to add effect to track: {str(e)}")

    # --- Knowledge Enrichment Tools ---
    @mcp_instance.tool()
    async def find_similar_tracks(
        track_uuid: str,
        max_results: int = 5,
        group_ids: Optional[List[str]] = None,
    ) -> Union[Dict[str, Any], ErrorResponse]:
        """Find tracks similar to the given track based on shared attributes or relationships."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify track exists
            track = await graphiti_client_instance.get_entity_node(track_uuid)
            if not track or "Track" not in track.labels:
                return ErrorResponse(error="Track not found or invalid entity type")
            
            effective_group_ids = group_ids or ["music"]
            
            # Get track attributes to search for
            search_attributes = []
            if track.attributes.get("genre"):
                search_attributes.append(track.attributes["genre"])
            if "mood" in track.attributes and track.attributes["mood"]:
                search_attributes.extend(track.attributes["mood"])
            if "key" in track.attributes and track.attributes["key"]:
                search_attributes.append(track.attributes["key"])
            
            if not search_attributes:
                # If no attributes to search by, try to use title as fallback
                if "title" in track.attributes:
                    search_attributes.append(track.attributes["title"])
            
            # Build search query from attributes
            search_query = " ".join(search_attributes)
            if not search_query:
                return ErrorResponse(error="Insufficient track metadata for similarity search")
            
            # Set up search filter for Track label
            filters = SearchFilters(node_labels=["Track"])
            
            # Execute search with the filter
            search_results = await graphiti_client_instance._search(
                query=search_query,
                group_ids=effective_group_ids,
                search_config=NODE_HYBRID_SEARCH_RRF,
                search_filters=filters,
                max_results=max_results + 1  # +1 to account for the track itself
            )
            
            # Filter out the original track
            similar_tracks = [
                node for node in search_results.nodes 
                if str(node.uuid) != track_uuid
            ][:max_results]
            
            # Format results
            formatted_results = [format_entity_result(node) for node in similar_tracks]
            
            return {
                "message": f"Found {len(formatted_results)} tracks similar to '{track.attributes.get('title', 'unknown')}'",
                "original_track": format_entity_result(track),
                "similar_tracks": formatted_results
            }
            
        except Exception as e:
            logger.error(f"Error finding similar tracks: {e}")
            return ErrorResponse(error=f"Failed to find similar tracks: {str(e)}")

    @mcp_instance.tool()
    async def get_artist_collaborators(
        artist_uuid: str,
        max_results: int = 10,
        group_ids: Optional[List[str]] = None,
    ) -> Union[Dict[str, Any], ErrorResponse]:
        """Find artists who have collaborated with the given artist on tracks."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify artist exists
            artist = await graphiti_client_instance.get_entity_node(artist_uuid)
            if not artist or "Artist" not in artist.labels:
                return ErrorResponse(error="Artist not found or invalid entity type")
            
            effective_group_ids = group_ids or ["music"]
            
            # First, get all tracks by this artist
            tracks_edges = await graphiti_client_instance.get_entity_edges_by_node(
                node_uuid=artist_uuid,
                relationship_type="PERFORMED_ON",
                group_ids=effective_group_ids,
                direction="outgoing"
            )
            
            if not tracks_edges:
                return {
                    "message": f"No tracks found for artist {artist.attributes.get('name', 'unknown')}",
                    "collaborators": []
                }
            
            # Collect all track UUIDs
            track_uuids = [edge.target_node_uuid for edge in tracks_edges]
            
            # Now find other artists who performed on these tracks
            collaborator_artists = {}
            
            for track_uuid in track_uuids:
                # Get artist relationships for this track
                artist_edges = await graphiti_client_instance.get_entity_edges_by_node(
                    node_uuid=track_uuid,
                    relationship_type="PERFORMED_ON",
                    group_ids=effective_group_ids,
                    direction="incoming"
                )
                
                # Get artist nodes from the edges
                for edge in artist_edges:
                    # Skip if it's the original artist
                    if edge.source_node_uuid == artist_uuid:
                        continue
                    
                    # Get the artist node
                    collab_artist = await graphiti_client_instance.get_entity_node(edge.source_node_uuid)
                    if collab_artist and "Artist" in collab_artist.labels:
                        # Add to dictionary with count of collaborations
                        if edge.source_node_uuid in collaborator_artists:
                            collaborator_artists[edge.source_node_uuid]["count"] += 1
                        else:
                            collaborator_artists[edge.source_node_uuid] = {
                                "artist": collab_artist,
                                "count": 1
                            }
            
            # Sort collaborators by collaboration count
            sorted_collaborators = sorted(
                collaborator_artists.values(),
                key=lambda x: x["count"],
                reverse=True
            )[:max_results]
            
            # Format results
            formatted_results = [
                {
                    **format_entity_result(item["artist"]),
                    "collaboration_count": item["count"]
                }
                for item in sorted_collaborators
            ]
            
            return {
                "message": f"Found {len(formatted_results)} collaborators for artist {artist.attributes.get('name', 'unknown')}",
                "artist": format_entity_result(artist),
                "collaborators": formatted_results
            }
            
        except Exception as e:
            logger.error(f"Error finding artist collaborators: {e}")
            return ErrorResponse(error=f"Failed to find artist collaborators: {str(e)}") 