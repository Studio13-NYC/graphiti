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
from .music_tools import (
    ErrorResponse, SuccessResponse, EntityResponse, EntitySearchResponse,
    RelationshipResponse, format_entity_result, format_relationship_result
)

logger = logging.getLogger(__name__)

# --- Global Instances (To be set by register_music_tools_part2) ---
graphiti_client_instance: Optional[Graphiti] = None
mcp_instance: Optional[FastMCP] = None

# --- Register Track and Other Entity Tools ---
def register_music_tools_part2(mcp: FastMCP, graphiti_client: Graphiti):
    """Register additional music entity tools with the FastMCP instance."""
    global graphiti_client_instance, mcp_instance
    graphiti_client_instance = graphiti_client
    mcp_instance = mcp

    if not mcp_instance:
        raise ValueError("MCP instance not set before registering music tools")

    # --- Track Tools ---
    @mcp_instance.tool()
    async def add_track(
        title: str,
        duration_ms: Optional[int] = None,
        explicit: Optional[bool] = None,
        popularity: Optional[int] = None,
        preview_url: Optional[str] = None,
        isrc: Optional[str] = None,
        lyrics: Optional[str] = None,
        tempo: Optional[float] = None,
        key: Optional[str] = None,
        genre: Optional[str] = None,
        spotify_uri: Optional[str] = None,
        spotify_url: Optional[str] = None,
        mood: Optional[str] = None,  # Comma-separated string
        release_date: Optional[str] = None,
        writers: Optional[str] = None,  # Comma-separated string
        producers: Optional[str] = None,  # Comma-separated string
        recording_date: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> Union[EntityResponse, ErrorResponse]:
        """Add a new track entity to the graph."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Process list fields
            mood_list = mood.split(",") if mood else None
            writers_list = writers.split(",") if writers else None
            producers_list = producers.split(",") if producers else None
            
            # Create track data
            track_data = {
                "title": title,
                "duration_ms": duration_ms,
                "explicit": explicit,
                "popularity": popularity,
                "preview_url": preview_url,
                "isrc": isrc,
                "lyrics": lyrics,
                "tempo": tempo,
                "key": key,
                "genre": genre,
                "spotify_uri": spotify_uri,
                "spotify_url": spotify_url,
                "mood": mood_list,
                "release_date": release_date,
                "writers": writers_list,
                "producers": producers_list,
                "recording_date": recording_date,
                "schema_version": "1.0"
            }
            # Filter out None values
            track_data = {k: v for k, v in track_data.items() if v is not None}
            
            # Create the track node
            episode_body = json.dumps({"Track": track_data})
            effective_group_id = group_id or "music"
            
            # Add as JSON episode
            result = await graphiti_client_instance.add_episode(
                name=f"Track: {title}",
                episode_body=episode_body,
                source=EpisodeType.json,
                group_id=effective_group_id,
                entity_types={"Track": Track}
            )
            
            # Extract the created track node
            track_nodes = [node for node in result.nodes if "Track" in node.labels]
            if not track_nodes:
                return ErrorResponse(error="Track creation failed: no track node found in result")
            
            return format_entity_result(track_nodes[0])
            
        except Exception as e:
            logger.error(f"Error creating track: {e}")
            return ErrorResponse(error=f"Track creation failed: {str(e)}")

    @mcp_instance.tool()
    async def get_track(
        uuid_str: str
    ) -> Union[EntityResponse, ErrorResponse]:
        """Get a track by UUID."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            entity = await graphiti_client_instance.get_entity_node(uuid_str)
            if not entity or "Track" not in entity.labels:
                return ErrorResponse(error="Track not found or invalid entity type")
            
            return format_entity_result(entity)
            
        except Exception as e:
            logger.error(f"Error getting track: {e}")
            return ErrorResponse(error=f"Error retrieving track: {str(e)}")

    @mcp_instance.tool()
    async def search_tracks(
        query: str,
        group_ids: Optional[List[str]] = None,
        max_results: int = 10
    ) -> Union[EntitySearchResponse, ErrorResponse]:
        """Search for tracks matching the query."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Set up search filter for Track label
            filters = SearchFilters(node_labels=["Track"])
            
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
                message=f"Found {len(formatted_results)} tracks matching '{query}'",
                entities=formatted_results
            )
            
        except Exception as e:
            logger.error(f"Error searching tracks: {e}")
            return ErrorResponse(error=f"Track search failed: {str(e)}")

    @mcp_instance.tool()
    async def update_track(
        uuid_str: str,
        title: Optional[str] = None,
        duration_ms: Optional[int] = None,
        explicit: Optional[bool] = None,
        popularity: Optional[int] = None,
        preview_url: Optional[str] = None,
        isrc: Optional[str] = None,
        lyrics: Optional[str] = None,
        tempo: Optional[float] = None,
        key: Optional[str] = None,
        genre: Optional[str] = None,
        spotify_uri: Optional[str] = None,
        spotify_url: Optional[str] = None,
        mood: Optional[str] = None,  # Comma-separated string
        release_date: Optional[str] = None,
        writers: Optional[str] = None,  # Comma-separated string
        producers: Optional[str] = None,  # Comma-separated string
        recording_date: Optional[str] = None,
    ) -> Union[EntityResponse, ErrorResponse]:
        """Update an existing track by UUID."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Get current track
            entity = await graphiti_client_instance.get_entity_node(uuid_str)
            if not entity or "Track" not in entity.labels:
                return ErrorResponse(error="Track not found or invalid entity type")
            
            # Process list fields
            mood_list = mood.split(",") if mood else None
            writers_list = writers.split(",") if writers else None
            producers_list = producers.split(",") if producers else None
            
            # Create update data with only the provided fields
            update_data = {}
            if title is not None: update_data["title"] = title
            if duration_ms is not None: update_data["duration_ms"] = duration_ms
            if explicit is not None: update_data["explicit"] = explicit
            if popularity is not None: update_data["popularity"] = popularity
            if preview_url is not None: update_data["preview_url"] = preview_url
            if isrc is not None: update_data["isrc"] = isrc
            if lyrics is not None: update_data["lyrics"] = lyrics
            if tempo is not None: update_data["tempo"] = tempo
            if key is not None: update_data["key"] = key
            if genre is not None: update_data["genre"] = genre
            if spotify_uri is not None: update_data["spotify_uri"] = spotify_uri
            if spotify_url is not None: update_data["spotify_url"] = spotify_url
            if mood_list is not None: update_data["mood"] = mood_list
            if release_date is not None: update_data["release_date"] = release_date
            if writers_list is not None: update_data["writers"] = writers_list
            if producers_list is not None: update_data["producers"] = producers_list
            if recording_date is not None: update_data["recording_date"] = recording_date
            
            if not update_data:
                return ErrorResponse(error="No update data provided")
            
            # Update the entity
            updated_entity = await graphiti_client_instance.update_entity_node(
                uuid_str=uuid_str,
                attributes=update_data
            )
            
            return format_entity_result(updated_entity)
            
        except Exception as e:
            logger.error(f"Error updating track: {e}")
            return ErrorResponse(error=f"Track update failed: {str(e)}")

    @mcp_instance.tool()
    async def delete_track(
        uuid_str: str
    ) -> Union[SuccessResponse, ErrorResponse]:
        """Delete a track by UUID."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify it's a track
            entity = await graphiti_client_instance.get_entity_node(uuid_str)
            if not entity or "Track" not in entity.labels:
                return ErrorResponse(error="Track not found or invalid entity type")
            
            # Delete the entity
            await graphiti_client_instance.delete_entity_node(uuid_str)
            
            return SuccessResponse(message=f"Track {entity.attributes.get('title', 'unknown')} deleted successfully")
            
        except Exception as e:
            logger.error(f"Error deleting track: {e}")
            return ErrorResponse(error=f"Track deletion failed: {str(e)}")

    # --- Relationship Tools ---
    @mcp_instance.tool()
    async def add_track_to_album(
        track_uuid: str,
        album_uuid: str,
        track_number: Optional[int] = None,
        disc_number: Optional[int] = None,
        group_id: Optional[str] = None,
    ) -> Union[RelationshipResponse, ErrorResponse]:
        """Create a relationship between a track and an album."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify entities exist and are of correct type
            track = await graphiti_client_instance.get_entity_node(track_uuid)
            album = await graphiti_client_instance.get_entity_node(album_uuid)
            
            if not track or "Track" not in track.labels:
                return ErrorResponse(error="Track not found or invalid entity type")
            
            if not album or "Album" not in album.labels:
                return ErrorResponse(error="Album not found or invalid entity type")
            
            # Create relationship attributes
            attributes = {}
            if track_number is not None:
                attributes["track_number"] = track_number
            if disc_number is not None:
                attributes["disc_number"] = disc_number
            
            effective_group_id = group_id or "music"
            
            # Create the relationship
            edge = await graphiti_client_instance.add_entity_edge(
                source_node_uuid=album_uuid,
                target_node_uuid=track_uuid,
                relationship_type="CONTAINS_TRACK",
                attributes=attributes,
                group_id=effective_group_id
            )
            
            return format_relationship_result(edge)
            
        except Exception as e:
            logger.error(f"Error creating track-album relationship: {e}")
            return ErrorResponse(error=f"Failed to add track to album: {str(e)}")

    @mcp_instance.tool()
    async def assign_artist_to_track(
        artist_uuid: str,
        track_uuid: str,
        role: Optional[str] = "primary_artist",
        contribution_details: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> Union[RelationshipResponse, ErrorResponse]:
        """Create a relationship between an artist and a track."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify entities exist and are of correct type
            artist = await graphiti_client_instance.get_entity_node(artist_uuid)
            track = await graphiti_client_instance.get_entity_node(track_uuid)
            
            if not artist or "Artist" not in artist.labels:
                return ErrorResponse(error="Artist not found or invalid entity type")
            
            if not track or "Track" not in track.labels:
                return ErrorResponse(error="Track not found or invalid entity type")
            
            # Create relationship attributes
            attributes = {"role": role}
            if contribution_details:
                attributes["contribution_details"] = contribution_details
            
            effective_group_id = group_id or "music"
            
            # Create the relationship
            edge = await graphiti_client_instance.add_entity_edge(
                source_node_uuid=artist_uuid,
                target_node_uuid=track_uuid,
                relationship_type="PERFORMED_ON",
                attributes=attributes,
                group_id=effective_group_id
            )
            
            return format_relationship_result(edge)
            
        except Exception as e:
            logger.error(f"Error creating artist-track relationship: {e}")
            return ErrorResponse(error=f"Failed to assign artist to track: {str(e)}")

    @mcp_instance.tool()
    async def assign_label_to_album(
        label_uuid: str,
        album_uuid: str,
        release_date: Optional[str] = None,
        catalog_number: Optional[str] = None,
        group_id: Optional[str] = None,
    ) -> Union[RelationshipResponse, ErrorResponse]:
        """Create a relationship between a label and an album."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify entities exist and are of correct type
            label = await graphiti_client_instance.get_entity_node(label_uuid)
            album = await graphiti_client_instance.get_entity_node(album_uuid)
            
            if not label or "Label" not in label.labels:
                return ErrorResponse(error="Label not found or invalid entity type")
            
            if not album or "Album" not in album.labels:
                return ErrorResponse(error="Album not found or invalid entity type")
            
            # Create relationship attributes
            attributes = {}
            if release_date:
                attributes["release_date"] = release_date
            if catalog_number:
                attributes["catalog_number"] = catalog_number
            
            effective_group_id = group_id or "music"
            
            # Create the relationship
            edge = await graphiti_client_instance.add_entity_edge(
                source_node_uuid=label_uuid,
                target_node_uuid=album_uuid,
                relationship_type="RELEASED",
                attributes=attributes,
                group_id=effective_group_id
            )
            
            return format_relationship_result(edge)
            
        except Exception as e:
            logger.error(f"Error creating label-album relationship: {e}")
            return ErrorResponse(error=f"Failed to assign label to album: {str(e)}")

    # --- Query Relationship Tools ---
    @mcp_instance.tool()
    async def get_album_tracks(
        album_uuid: str,
        group_ids: Optional[List[str]] = None,
    ) -> Union[EntitySearchResponse, ErrorResponse]:
        """Get all tracks on an album."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify album exists
            album = await graphiti_client_instance.get_entity_node(album_uuid)
            if not album or "Album" not in album.labels:
                return ErrorResponse(error="Album not found or invalid entity type")
            
            effective_group_ids = group_ids or ["music"]
            
            # Get all outgoing relationships of type CONTAINS_TRACK
            edges = await graphiti_client_instance.get_entity_edges_by_node(
                node_uuid=album_uuid,
                relationship_type="CONTAINS_TRACK",
                group_ids=effective_group_ids,
                direction="outgoing"
            )
            
            if not edges:
                return EntitySearchResponse(
                    message=f"No tracks found for album {album.attributes.get('title', 'unknown')}",
                    entities=[]
                )
            
            # Get all track nodes from the relationships
            track_uuids = [edge.target_node_uuid for edge in edges]
            tracks = []
            
            for uuid_str in track_uuids:
                track = await graphiti_client_instance.get_entity_node(uuid_str)
                if track and "Track" in track.labels:
                    tracks.append(track)
            
            return EntitySearchResponse(
                message=f"Found {len(tracks)} tracks for album {album.attributes.get('title', 'unknown')}",
                entities=[format_entity_result(track) for track in tracks]
            )
            
        except Exception as e:
            logger.error(f"Error getting album tracks: {e}")
            return ErrorResponse(error=f"Failed to get album tracks: {str(e)}")

    @mcp_instance.tool()
    async def get_artist_tracks(
        artist_uuid: str,
        group_ids: Optional[List[str]] = None,
    ) -> Union[EntitySearchResponse, ErrorResponse]:
        """Get all tracks by an artist."""
        if not graphiti_client_instance:
            return ErrorResponse(error="Graphiti client not initialized")
        
        try:
            # Verify artist exists
            artist = await graphiti_client_instance.get_entity_node(artist_uuid)
            if not artist or "Artist" not in artist.labels:
                return ErrorResponse(error="Artist not found or invalid entity type")
            
            effective_group_ids = group_ids or ["music"]
            
            # Get all outgoing relationships of type PERFORMED_ON
            edges = await graphiti_client_instance.get_entity_edges_by_node(
                node_uuid=artist_uuid,
                relationship_type="PERFORMED_ON",
                group_ids=effective_group_ids,
                direction="outgoing"
            )
            
            if not edges:
                return EntitySearchResponse(
                    message=f"No tracks found for artist {artist.attributes.get('name', 'unknown')}",
                    entities=[]
                )
            
            # Get all track nodes from the relationships
            track_uuids = [edge.target_node_uuid for edge in edges]
            tracks = []
            
            for uuid_str in track_uuids:
                track = await graphiti_client_instance.get_entity_node(uuid_str)
                if track and "Track" in track.labels:
                    tracks.append(track)
            
            return EntitySearchResponse(
                message=f"Found {len(tracks)} tracks for artist {artist.attributes.get('name', 'unknown')}",
                entities=[format_entity_result(track) for track in tracks]
            )
            
        except Exception as e:
            logger.error(f"Error getting artist tracks: {e}")
            return ErrorResponse(error=f"Failed to get artist tracks: {str(e)}")

    # --- Other Entity Types ---
    # Similar implementations for Equipment, Studio, Person, Credit, Label, Performance, Effect
    # would follow the same pattern as the Artist, Album, and Track implementations above 