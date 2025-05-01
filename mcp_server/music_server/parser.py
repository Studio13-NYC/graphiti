"""
Universal Music Data Parser for Graphiti MCP Server.

This module provides a universal parser that can extract music entities from various
data formats (text, JSON, structured API responses) and store them in the knowledge graph.
"""

import asyncio
import json
import logging
import re
import sys
import os
from typing import Any, Dict, List, Optional, Union, Tuple

# Add the parent directory to the path to allow imports when run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType, EntityNode
from graphiti_core.edges import EntityEdge

# Try absolute imports first, then fall back to relative imports
try:
    from mcp_server.music_server.models.music import (
        Artist, Album, Track, Equipment, Studio, Person, 
        Credit, Label, Performance, Effect
    )
except ImportError:
    # If absolute imports fail, try relative imports
    from .models.music import (
        Artist, Album, Track, Equipment, Studio, Person, 
        Credit, Label, Performance, Effect
    )

logger = logging.getLogger(__name__)

# Entity type mapping for model instantiation
ENTITY_TYPE_MAP = {
    "Artist": Artist,
    "Album": Album,
    "Track": Track,
    "Equipment": Equipment,
    "Studio": Studio,
    "Person": Person,
    "Credit": Credit,
    "Label": Label,
    "Performance": Performance,
    "Effect": Effect
}

# Relationship type mapping to guide relationship inference
RELATIONSHIP_PATTERNS = [
    # Artist -> Album relationships
    {"source": "Artist", "target": "Album", "type": "CREATED_ALBUM"},
    # Album -> Track relationships
    {"source": "Album", "target": "Track", "type": "CONTAINS_TRACK"},
    # Artist -> Track relationships
    {"source": "Artist", "target": "Track", "type": "PERFORMED_ON"},
    # Equipment -> Track relationships
    {"source": "Equipment", "target": "Track", "type": "USED_ON"},
    # Studio -> Album relationships
    {"source": "Studio", "target": "Album", "type": "RECORDED_AT"},
    # Person -> Album relationships (producer)
    {"source": "Person", "target": "Album", "type": "PRODUCED"},
    # Person -> Track relationships (engineer)
    {"source": "Person", "target": "Track", "type": "ENGINEERED"},
    # Label -> Album relationships
    {"source": "Label", "target": "Album", "type": "RELEASED"},
    # Artist -> Performance relationships
    {"source": "Artist", "target": "Performance", "type": "PERFORMED_AT"},
    # Track -> Performance relationships
    {"source": "Track", "target": "Performance", "type": "PERFORMED_IN"},
    # Effect -> Track relationships
    {"source": "Effect", "target": "Track", "type": "APPLIED_TO"},
]

class MusicDataParser:
    """Universal parser for music-related data."""
    
    def __init__(self, graphiti_client: Graphiti, llm_client):
        """
        Initialize the music data parser.
        
        Args:
            graphiti_client: Initialized Graphiti client
            llm_client: LLM client for text parsing
        """
        self.graphiti_client = graphiti_client
        self.llm_client = llm_client
    
    async def parse_and_store(
        self, 
        data: str,
        format_hint: Optional[str] = None,
        extract_relationships: bool = True,
        dedup_strategy: str = "update_if_exists",
        group_id: str = "music"
    ) -> Dict[str, Any]:
        """
        Main entry point for parsing music data.
        
        Args:
            data: The raw data containing music information to parse
            format_hint: Optional hint about data format to guide parsing
            extract_relationships: Whether to automatically create relationships
            dedup_strategy: How to handle potential duplicates
            group_id: Group ID for storing the extracted entities
            
        Returns:
            Dictionary with extraction results details
        """
        # Detect format if not provided
        if not format_hint:
            format_hint = self._detect_format(data)
        
        # Extract entities based on format
        extracted_entities = await self._parse_data(data, format_hint)
        
        # Store entities
        created_entities = await self._store_entities(
            extracted_entities, 
            dedup_strategy,
            group_id
        )
        
        # Create relationships if requested
        relationships = []
        if extract_relationships and len(created_entities) > 1:
            relationships = await self._infer_relationships(
                created_entities,
                group_id
            )
        
        return {
            "message": f"Processed music data and created {len(created_entities)} entities and {len(relationships)} relationships",
            "entities": created_entities,
            "relationships": relationships
        }
    
    def _detect_format(self, data: str) -> str:
        """
        Detect the format of input data.
        
        Args:
            data: Raw input data
            
        Returns:
            Format hint string ("json", "text", "spotify", etc.)
        """
        # Try to parse as JSON
        try:
            json.loads(data)
            return "json"
        except json.JSONDecodeError:
            pass
        
        # Check for Spotify API patterns
        if '"type": "artist"' in data or '"type": "album"' in data or '"type": "track"' in data:
            return "spotify"
        
        # Default to text
        return "text"
    
    async def _parse_data(self, data: str, format_hint: str) -> List[Dict[str, Any]]:
        """
        Parse the data based on its format.
        
        Args:
            data: Raw input data
            format_hint: Format hint ("json", "text", "spotify", etc.)
            
        Returns:
            List of extracted entity dictionaries
        """
        if format_hint == "json":
            return await self._parse_json(data)
        elif format_hint == "spotify":
            return await self._parse_spotify(data)
        else:  # Default to text
            return await self._parse_text(data)
    
    async def _parse_json(self, data: str) -> List[Dict[str, Any]]:
        """
        Parse JSON-formatted music data.
        
        Args:
            data: JSON string
            
        Returns:
            List of extracted entity dictionaries
        """
        try:
            json_data = json.loads(data)
            extracted_entities = []
            
            # Handle different JSON structures
            if isinstance(json_data, dict):
                # Single entity or nested structure
                entity_type = None
                
                # Try to detect entity type
                if "name" in json_data and ("biography" in json_data or "genres" in json_data):
                    entity_type = "Artist"
                elif "title" in json_data and ("release_date" in json_data or "album_type" in json_data):
                    entity_type = "Album"
                elif "title" in json_data and ("duration_ms" in json_data or "isrc" in json_data):
                    entity_type = "Track"
                
                # Process based on detected type
                if entity_type:
                    extracted_entities.append({"entity_type": entity_type, "attributes": json_data})
                
                # Check for nested entities
                if "artist" in json_data or "artists" in json_data:
                    artists = json_data.get("artists", []) or [json_data.get("artist")] if json_data.get("artist") else []
                    if isinstance(artists, str):
                        artists = [{"name": artists}]
                    for artist in artists:
                        if isinstance(artist, str):
                            artist = {"name": artist}
                        extracted_entities.append({"entity_type": "Artist", "attributes": artist})
                
                if "album" in json_data:
                    album = json_data.get("album")
                    if isinstance(album, str):
                        album = {"title": album}
                        extracted_entities.append({"entity_type": "Album", "attributes": album})
                
                if "tracks" in json_data:
                    tracks = json_data.get("tracks", [])
                    for track in tracks:
                        if isinstance(track, str):
                            track = {"title": track}
                        extracted_entities.append({"entity_type": "Track", "attributes": track})
            
            elif isinstance(json_data, list):
                # List of entities
                for item in json_data:
                    if isinstance(item, dict):
                        # Detect entity type
                        entity_type = None
                        if "name" in item and ("biography" in item or "genres" in item):
                            entity_type = "Artist"
                        elif "title" in item and ("release_date" in item or "album_type" in item):
                            entity_type = "Album"
                        elif "title" in item and ("duration_ms" in item or "isrc" in item):
                            entity_type = "Track"
                        
                        if entity_type:
                            extracted_entities.append({"entity_type": entity_type, "attributes": item})
            
            return extracted_entities
            
        except Exception as e:
            logger.error(f"Error parsing JSON data: {e}")
            return []
    
    async def _parse_spotify(self, data: str) -> List[Dict[str, Any]]:
        """
        Parse Spotify API response data.
        
        Args:
            data: JSON string from Spotify API
            
        Returns:
            List of extracted entity dictionaries
        """
        try:
            spotify_data = json.loads(data)
            extracted_entities = []
            
            # Process based on Spotify object types
            if "type" in spotify_data:
                if spotify_data["type"] == "artist":
                    # Convert Spotify artist to our Artist model
                    artist_data = {
                        "name": spotify_data.get("name"),
                        "genres": spotify_data.get("genres"),
                        "popularity": spotify_data.get("popularity"),
                        "followers": spotify_data.get("followers", {}).get("total") if isinstance(spotify_data.get("followers"), dict) else None,
                        "spotify_uri": spotify_data.get("uri"),
                        "spotify_url": spotify_data.get("external_urls", {}).get("spotify") if isinstance(spotify_data.get("external_urls"), dict) else None,
                        "image_url": spotify_data.get("images", [{}])[0].get("url") if spotify_data.get("images") else None
                    }
                    extracted_entities.append({"entity_type": "Artist", "attributes": artist_data})
                    
                elif spotify_data["type"] == "album":
                    # Convert Spotify album to our Album model
                    album_data = {
                        "title": spotify_data.get("name"),
                        "release_date": spotify_data.get("release_date"),
                        "album_type": spotify_data.get("album_type"),
                        "total_tracks": spotify_data.get("total_tracks"),
                        "release_date_precision": spotify_data.get("release_date_precision"),
                        "spotify_uri": spotify_data.get("uri"),
                        "spotify_url": spotify_data.get("external_urls", {}).get("spotify") if isinstance(spotify_data.get("external_urls"), dict) else None,
                        "images": spotify_data.get("images")
                    }
                    extracted_entities.append({"entity_type": "Album", "attributes": album_data})
                    
                    # Extract artists if present
                    if "artists" in spotify_data and isinstance(spotify_data["artists"], list):
                        for artist in spotify_data["artists"]:
                            artist_data = {
                                "name": artist.get("name"),
                                "spotify_uri": artist.get("uri"),
                                "spotify_url": artist.get("external_urls", {}).get("spotify") if isinstance(artist.get("external_urls"), dict) else None
                            }
                            extracted_entities.append({"entity_type": "Artist", "attributes": artist_data})
                    
                    # Extract tracks if present
                    if "tracks" in spotify_data and "items" in spotify_data["tracks"]:
                        for track in spotify_data["tracks"]["items"]:
                            track_data = {
                                "title": track.get("name"),
                                "duration_ms": track.get("duration_ms"),
                                "explicit": track.get("explicit"),
                                "preview_url": track.get("preview_url"),
                                "spotify_uri": track.get("uri"),
                                "spotify_url": track.get("external_urls", {}).get("spotify") if isinstance(track.get("external_urls"), dict) else None
                            }
                            extracted_entities.append({"entity_type": "Track", "attributes": track_data})
                            
                            # Extract track artists if present
                            if "artists" in track and isinstance(track["artists"], list):
                                for artist in track["artists"]:
                                    artist_data = {
                                        "name": artist.get("name"),
                                        "spotify_uri": artist.get("uri"),
                                        "spotify_url": artist.get("external_urls", {}).get("spotify") if isinstance(artist.get("external_urls"), dict) else None
                                    }
                                    extracted_entities.append({"entity_type": "Artist", "attributes": artist_data})
                
                elif spotify_data["type"] == "track":
                    # Convert Spotify track to our Track model
                    track_data = {
                        "title": spotify_data.get("name"),
                        "duration_ms": spotify_data.get("duration_ms"),
                        "explicit": spotify_data.get("explicit"),
                        "popularity": spotify_data.get("popularity"),
                        "preview_url": spotify_data.get("preview_url"),
                        "spotify_uri": spotify_data.get("uri"),
                        "spotify_url": spotify_data.get("external_urls", {}).get("spotify") if isinstance(spotify_data.get("external_urls"), dict) else None
                    }
                    extracted_entities.append({"entity_type": "Track", "attributes": track_data})
                    
                    # Extract album if present
                    if "album" in spotify_data and isinstance(spotify_data["album"], dict):
                        album_data = {
                            "title": spotify_data["album"].get("name"),
                            "album_type": spotify_data["album"].get("album_type"),
                            "release_date": spotify_data["album"].get("release_date"),
                            "spotify_uri": spotify_data["album"].get("uri"),
                            "spotify_url": spotify_data["album"].get("external_urls", {}).get("spotify") if isinstance(spotify_data["album"].get("external_urls"), dict) else None,
                            "images": spotify_data["album"].get("images")
                        }
                        extracted_entities.append({"entity_type": "Album", "attributes": album_data})
                    
                    # Extract artists if present
                    if "artists" in spotify_data and isinstance(spotify_data["artists"], list):
                        for artist in spotify_data["artists"]:
                            artist_data = {
                                "name": artist.get("name"),
                                "spotify_uri": artist.get("uri"),
                                "spotify_url": artist.get("external_urls", {}).get("spotify") if isinstance(artist.get("external_urls"), dict) else None
                            }
                            extracted_entities.append({"entity_type": "Artist", "attributes": artist_data})
            
            return extracted_entities
            
        except Exception as e:
            logger.error(f"Error parsing Spotify data: {e}")
            return []
    
    async def _parse_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Parse unstructured text to extract music entities.
        
        Args:
            text: Unstructured text string
            
        Returns:
            List of extracted entity dictionaries
        """
        try:
            # Use LLM to extract structured information from text
            llm_prompt = f"""
            Extract music entities from the following text. Identify any artists, albums, tracks, studios, 
            equipment, people (producers, engineers), labels, performances, or effects mentioned.
            
            For each entity, determine its type and relevant attributes according to the schema below.
            Return the results as a JSON array of entities with their types and attributes.
            
            Entity Types and Key Attributes:
            - Artist: name, biography, genres, active_years, country
            - Album: title, release_date, album_type, total_tracks
            - Track: title, duration_ms, explicit, popularity, lyrics, tempo, key
            - Equipment: name, type, manufacturer, model, year
            - Studio: name, location, founding_date
            - Person: name, roles (comma-separated)
            - Credit: role_name, contribution_details
            - Label: name, founding_date, parent_company
            - Performance: venue, date, setlist (comma-separated)
            - Effect: name, type, parameters
            
            Text: {text}
            
            Output JSON array:
            """
            
            llm_response = await self.llm_client.chat_completion(
                model="gpt-4o",  # Use appropriate model
                messages=[
                    {"role": "system", "content": "You are a music information extraction system."},
                    {"role": "user", "content": llm_prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            # Extract JSON from LLM response
            response_content = llm_response.choices[0].message.content
            
            try:
                # Try to parse as JSON object with 'entities' field
                parsed_response = json.loads(response_content)
                if isinstance(parsed_response, dict) and "entities" in parsed_response:
                    extracted_entities = []
                    for entity in parsed_response["entities"]:
                        if "type" in entity and "attributes" in entity:
                            extracted_entities.append({
                                "entity_type": entity["type"],
                                "attributes": entity["attributes"]
                            })
                        elif "type" in entity:
                            # If attributes not explicitly separated
                            attributes = {k: v for k, v in entity.items() if k != "type"}
                            extracted_entities.append({
                                "entity_type": entity["type"],
                                "attributes": attributes
                            })
                    return extracted_entities
                elif isinstance(parsed_response, list):
                    # Direct list of entities
                    extracted_entities = []
                    for entity in parsed_response:
                        if "type" in entity and "attributes" in entity:
                            extracted_entities.append({
                                "entity_type": entity["type"],
                                "attributes": entity["attributes"]
                            })
                        elif "type" in entity:
                            # If attributes not explicitly separated
                            attributes = {k: v for k, v in entity.items() if k != "type"}
                            extracted_entities.append({
                                "entity_type": entity["type"],
                                "attributes": attributes
                            })
                    return extracted_entities
                else:
                    logger.warning(f"Unexpected LLM response format: {response_content}")
                    return []
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON response: {e}")
                logger.error(f"Raw response: {response_content}")
                return []
                
        except Exception as e:
            logger.error(f"Error parsing text: {e}")
            return []
    
    async def _store_entities(
        self, 
        entities: List[Dict[str, Any]], 
        dedup_strategy: str,
        group_id: str
    ) -> List[Dict[str, Any]]:
        """
        Store extracted entities in the knowledge graph.
        
        Args:
            entities: List of entity dictionaries with type and attributes
            dedup_strategy: How to handle potential duplicates
            group_id: Group ID for storing entities
            
        Returns:
            List of created entity dictionaries with UUIDs
        """
        created_entities = []
        
        for entity_data in entities:
            entity_type = entity_data.get("entity_type")
            attributes = entity_data.get("attributes", {})
            
            if not entity_type or not attributes:
                logger.warning(f"Skipping invalid entity data: {entity_data}")
                continue
            
            if entity_type not in ENTITY_TYPE_MAP:
                logger.warning(f"Unknown entity type: {entity_type}")
                continue
            
            try:
                # Check for duplicates based on strategy
                existing_entity = None
                if dedup_strategy != "create_new":
                    existing_entity = await self._find_duplicate_entity(entity_type, attributes)
                
                if existing_entity and dedup_strategy == "skip":
                    # Skip this entity
                    created_entities.append({
                        "uuid": str(existing_entity.uuid),
                        "entity_type": entity_type,
                        "attributes": existing_entity.attributes,
                        "created_at": existing_entity.created_at.isoformat() if existing_entity.created_at else None,
                        "group_id": existing_entity.group_id,
                        "status": "skipped"
                    })
                    continue
                
                if existing_entity and dedup_strategy == "update_if_exists":
                    # Update existing entity
                    updated_attributes = {**existing_entity.attributes, **attributes}
                    updated_entity = await self.graphiti_client.update_entity_node(
                        str(existing_entity.uuid),
                        updated_attributes
                    )
                    created_entities.append({
                        "uuid": str(updated_entity.uuid),
                        "entity_type": entity_type,
                        "attributes": updated_entity.attributes,
                        "created_at": updated_entity.created_at.isoformat() if updated_entity.created_at else None,
                        "group_id": updated_entity.group_id,
                        "status": "updated"
                    })
                    continue
                
                # Create new entity
                # Prepare episode for creating entity
                entity_model = ENTITY_TYPE_MAP[entity_type]
                
                # Filter attributes to only include fields in the model
                valid_fields = set(entity_model.__fields__.keys())
                filtered_attributes = {k: v for k, v in attributes.items() if k in valid_fields}
                
                # Create episode body
                episode_body = json.dumps({entity_type: filtered_attributes})
                
                # Add as JSON episode
                result = await self.graphiti_client.add_episode(
                    name=f"{entity_type}: {filtered_attributes.get('name') or filtered_attributes.get('title')}",
                    episode_body=episode_body,
                    source=EpisodeType.json,
                    group_id=group_id,
                    entity_types={entity_type: ENTITY_TYPE_MAP[entity_type]}
                )
                
                # Extract the created entity node
                created_nodes = [node for node in result.nodes if entity_type in node.labels]
                if created_nodes:
                    node = created_nodes[0]
                    created_entities.append({
                        "uuid": str(node.uuid),
                        "entity_type": entity_type,
                        "attributes": node.attributes,
                        "created_at": node.created_at.isoformat() if node.created_at else None,
                        "group_id": node.group_id,
                        "status": "created"
                    })
            
            except Exception as e:
                logger.error(f"Error storing {entity_type} entity: {e}")
        
        return created_entities
    
    async def _find_duplicate_entity(
        self, 
        entity_type: str, 
        attributes: Dict[str, Any]
    ) -> Optional[EntityNode]:
        """
        Find potential duplicate entity based on type and key attributes.
        
        Args:
            entity_type: Entity type to check
            attributes: Entity attributes
            
        Returns:
            Existing entity node if found, None otherwise
        """
        # Define key fields for each entity type to use for deduplication
        key_fields = {
            "Artist": ["name", "spotify_uri"],
            "Album": ["title", "spotify_uri"],
            "Track": ["title", "isrc", "spotify_uri"],
            "Equipment": ["name", "manufacturer", "model"],
            "Studio": ["name", "location"],
            "Person": ["name"],
            "Credit": ["role_name"],
            "Label": ["name"],
            "Performance": ["venue", "date"],
            "Effect": ["name", "type"]
        }
        
        if entity_type not in key_fields:
            return None
        
        # Build Cypher query based on available key fields
        match_conditions = []
        params = {}
        
        for field in key_fields[entity_type]:
            if field in attributes and attributes[field]:
                match_conditions.append(f"n.{field} = ${field}")
                params[field] = attributes[field]
        
        if not match_conditions:
            return None
        
        # Construct and execute Cypher query
        cypher_query = f"""
        MATCH (n:{entity_type})
        WHERE {" OR ".join(match_conditions)}
        RETURN n
        LIMIT 1
        """
        
        try:
            result = await self.graphiti_client.run_cypher(cypher_query, params)
            if result and result[0]["n"]:
                return EntityNode.from_dict(result[0]["n"])
            return None
        except Exception as e:
            logger.error(f"Error finding duplicate for {entity_type}: {e}")
            return None
    
    async def _infer_relationships(
        self, 
        entities: List[Dict[str, Any]],
        group_id: str
    ) -> List[Dict[str, Any]]:
        """
        Infer and create relationships between entities.
        
        Args:
            entities: List of created entity dictionaries
            group_id: Group ID for relationships
            
        Returns:
            List of created relationship dictionaries
        """
        created_relationships = []
        
        # Group entities by type for easier processing
        entities_by_type = {}
        for entity in entities:
            entity_type = entity.get("entity_type")
            if entity_type not in entities_by_type:
                entities_by_type[entity_type] = []
            entities_by_type[entity_type].append(entity)
        
        # Apply relationship patterns
        for pattern in RELATIONSHIP_PATTERNS:
            source_type = pattern["source"]
            target_type = pattern["target"]
            rel_type = pattern["type"]
            
            if source_type not in entities_by_type or target_type not in entities_by_type:
                continue
            
            # Get all source and target entities
            source_entities = entities_by_type[source_type]
            target_entities = entities_by_type[target_type]
            
            # Create relationships based on pattern
            for source in source_entities:
                for target in target_entities:
                    # Skip self-relationships
                    if source["uuid"] == target["uuid"]:
                        continue
                    
                    # Check if relationship is logical based on attributes
                    if await self._should_create_relationship(source, target, rel_type):
                        try:
                            # Create the relationship
                            edge = await self.graphiti_client.create_entity_edge(
                                source_node_uuid=source["uuid"],
                                target_node_uuid=target["uuid"],
                                relationship_type=rel_type,
                                attributes={},
                                group_id=group_id
                            )
                            
                            created_relationships.append({
                                "uuid": str(edge.uuid),
                                "source_uuid": str(edge.source_node_uuid),
                                "target_uuid": str(edge.target_node_uuid),
                                "relationship_type": edge.relationship_type,
                                "attributes": edge.attributes,
                                "created_at": edge.created_at.isoformat() if edge.created_at else None,
                                "group_id": edge.group_id
                            })
                        except Exception as e:
                            logger.error(f"Error creating relationship: {e}")
        
        return created_relationships
    
    async def _should_create_relationship(
        self, 
        source: Dict[str, Any], 
        target: Dict[str, Any],
        relationship_type: str
    ) -> bool:
        """
        Determine if a relationship should be created between two entities.
        
        Args:
            source: Source entity dictionary
            target: Target entity dictionary
            relationship_type: Type of relationship
            
        Returns:
            True if relationship should be created, False otherwise
        """
        source_type = source.get("entity_type")
        target_type = target.get("entity_type")
        
        # Basic pattern matching logic - can be enhanced with more sophisticated rules
        if relationship_type == "CREATED_ALBUM" and source_type == "Artist" and target_type == "Album":
            # Check if artist name is mentioned in album attributes
            artist_name = source.get("attributes", {}).get("name", "").lower()
            album_description = target.get("attributes", {}).get("description", "").lower()
            
            if artist_name and (artist_name in album_description):
                return True
        
        elif relationship_type == "CONTAINS_TRACK" and source_type == "Album" and target_type == "Track":
            # Always connect tracks to albums for simplicity
            return True
        
        elif relationship_type == "PERFORMED_ON" and source_type == "Artist" and target_type == "Track":
            # Always connect artists to tracks for simplicity
            return True
        
        # Default to creating the relationship in the streamlined approach
        # More sophisticated rules could be added based on specific entity attributes
        return True 