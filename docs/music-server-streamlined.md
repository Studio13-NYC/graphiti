# Streamlined Music Knowledge Graph MCP Server

## Overview

This document outlines the implementation of a streamlined Graphiti Music Knowledge Graph MCP server. The core improvement is a universal music data parser that significantly reduces the number of exposed tools while maintaining full functionality.

## Architecture Changes

### Current Architecture

The current architecture implements numerous specialized tools:
- 10+ entity creation tools (`add_artist`, `add_album`, `add_track`, etc.)
- 8+ relationship creation tools
- 10+ entity-specific search tools
- Various utility tools

This approach has several drawbacks:
- High cognitive load for LLMs and users
- Redundant code paths
- Complex documentation
- Maintenance overhead
- Inconsistent parameter patterns

### Streamlined Architecture

The streamlined architecture reduces the tool set to a core set of universal tools:

1. **Universal Parser**: A single entry point for all music data
2. **Generic Entity Operations**: For when direct entity manipulation is needed
3. **Generic Relationship Operations**: For creating and managing relationships
4. **Unified Search**: Consistent search interfaces across entity types

## Core Components

### 1. Universal Music Data Parser

The centerpiece of the streamlined architecture is a universal parser that can handle any music-related data:

```python
@mcp_instance.tool()
async def parse_and_store_music_data(
    data: str,
    format_hint: Optional[str] = None,  # "json", "text", "spotify", etc.
    extract_relationships: bool = True,
    dedup_strategy: str = "update_if_exists",
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Parse any music-related data and store as appropriate entities in the knowledge graph.
    
    This tool intelligently processes various data formats (text, JSON, etc.) and extracts
    music entities like Artists, Albums, Tracks, Studios, etc. according to our established
    taxonomy. It can detect entity types, extract their attributes, and create appropriate
    relationships between them.
    
    Parameters:
    - data: The raw data containing music information to parse (can be JSON, text, etc.)
    - format_hint: Optional hint about data format to guide parsing ("json", "text", "spotify", etc.)
    - extract_relationships: Whether to automatically create relationships between detected entities
    - dedup_strategy: How to handle potential duplicates ("update_if_exists", "skip", "create_new")
    - group_id: Optional group ID for storing the extracted entities
    
    Returns details of all extracted entities and relationships.
    
    Examples:
    - Text: "Bohemian Rhapsody was recorded by Queen in 1975 for their album A Night at the Opera."
    - JSON: {"artist": "Taylor Swift", "album": "1989", "tracks": ["Shake It Off", "Blank Space"]}
    - Spotify API response: [Spotify album object with tracks]
    """
```

#### Implementation Details

The parser operates in two phases:
1. **Entity Extraction**: Identify potential entities and their attributes
   - For text input: Use LLM capabilities to extract structured data
   - For JSON/structured input: Map to entity models
   
2. **Entity Creation & Relationship Inference**:
   - Create or update entities in the graph
   - Infer and create relationships between entities
   - Verify against entity models

### 2. Consolidated Entity Tools

Replace multiple entity-specific tools with these generic operations:

```python
@mcp_instance.tool()
async def add_entity(
    entity_type: str,  # "Artist", "Album", "Track", etc.
    attributes: Dict[str, Any],
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Add a new entity of the specified type to the knowledge graph.
    
    Parameters:
    - entity_type: The type of entity to create (Artist, Album, Track, etc.)
    - attributes: Dictionary of entity attributes
    - group_id: Optional group ID for storing the entity
    """

@mcp_instance.tool()
async def update_entity(
    uuid: str,
    attributes: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Update an existing entity's attributes.
    
    Parameters:
    - uuid: Entity UUID
    - attributes: Dictionary of attributes to update
    """

@mcp_instance.tool()
async def delete_entity(
    uuid: str
) -> Dict[str, Any]:
    """
    Delete an entity from the knowledge graph.
    
    Parameters:
    - uuid: Entity UUID
    """

@mcp_instance.tool()
async def get_entity(
    uuid: str
) -> Dict[str, Any]:
    """
    Retrieve an entity by UUID.
    
    Parameters:
    - uuid: Entity UUID
    """
```

### 3. Simplified Relationship Tools

```python
@mcp_instance.tool()
async def create_relationship(
    source_uuid: str,
    target_uuid: str,
    relationship_type: str,
    attributes: Optional[Dict[str, Any]] = None,
    group_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a relationship between two entities.
    
    Parameters:
    - source_uuid: Source entity UUID
    - target_uuid: Target entity UUID
    - relationship_type: Type of relationship (e.g., "PERFORMED_ON", "CONTAINS_TRACK")
    - attributes: Optional attributes for the relationship
    - group_id: Optional group ID
    """

@mcp_instance.tool()
async def get_relationships(
    entity_uuid: str,
    relationship_type: Optional[str] = None,
    direction: str = "both",
    entity_types: Optional[List[str]] = None,
    group_ids: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Get relationships for an entity, with optional filtering.
    
    Parameters:
    - entity_uuid: Entity UUID
    - relationship_type: Optional relationship type filter
    - direction: "incoming", "outgoing", or "both"
    - entity_types: Optional list of entity types to filter related entities
    - group_ids: Optional group IDs to search within
    """
```

### 4. Unified Search

```python
@mcp_instance.tool()
async def search_entities(
    query: str,
    entity_types: Optional[List[str]] = None,
    group_ids: Optional[List[str]] = None,
    max_results: int = 10,
    center_entity_uuid: Optional[str] = None
) -> Dict[str, Any]:
    """
    Search for entities matching a query.
    
    Parameters:
    - query: Search query
    - entity_types: Optional list of entity types to search for
    - group_ids: Optional group IDs to search within
    - max_results: Maximum number of results to return
    - center_entity_uuid: Optional UUID to prioritize entities connected to this one
    """
```

## Implementation Approach

### Phase 1: Parser Implementation

1. Create the universal parser module (`parser.py`):
   ```python
   import asyncio
   import json
   import logging
   from typing import Any, Dict, List, Optional, Union
   
   from graphiti_core import Graphiti
   from graphiti_core.nodes import EpisodeType
   
   from .models.music import (
       Artist, Album, Track, Equipment, Studio, Person, 
       Credit, Label, Performance, Effect
   )
   
   logger = logging.getLogger(__name__)
   
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
   
   class MusicDataParser:
       def __init__(self, graphiti_client: Graphiti, llm_client):
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
           """Main entry point for parsing music data"""
           
           # Detect format if not provided
           if not format_hint:
               format_hint = self._detect_format(data)
           
           # Extract entities based on format
           if format_hint == "json":
               extracted_entities = await self._parse_json(data)
           else:  # Default to text
               extracted_entities = await self._parse_text(data)
           
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
       
       # Additional methods for specific parsing logic
       # ...
   ```

2. Implement specific parsing methods:
   - `_detect_format`: Determine if input is JSON, text, etc.
   - `_parse_text`: Use LLM to extract entities from text
   - `_parse_json`: Map JSON to entity models
   - `_store_entities`: Create/update entities in the graph
   - `_infer_relationships`: Create relationships between entities

### Phase 2: Tool Implementation

Implement the streamlined tools using the parser:

```python
@mcp_instance.tool()
async def parse_and_store_music_data(
    data: str,
    format_hint: Optional[str] = None,
    extract_relationships: bool = True,
    dedup_strategy: str = "update_if_exists",
    group_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse any music data and store as entities in the graph."""
    if not graphiti_client_instance:
        return {"error": "Graphiti client not initialized"}
    
    try:
        # Use the parser
        effective_group_id = group_id or "music"
        parser = MusicDataParser(graphiti_client_instance, llm_client)
        
        result = await parser.parse_and_store(
            data=data,
            format_hint=format_hint,
            extract_relationships=extract_relationships,
            dedup_strategy=dedup_strategy,
            group_id=effective_group_id
        )
        
        return result
    except Exception as e:
        logger.error(f"Error parsing music data: {e}")
        return {"error": f"Failed to parse music data: {str(e)}"}
```

### Phase 3: Integration & Testing

1. Replace entity-specific tools with the universal tools
2. Update server.py to register the new streamlined tool set
3. Create comprehensive test cases for various data formats

## Benefits

1. **Lower Cognitive Load**: LLMs have fewer tools to understand
2. **Flexibility**: Can handle a wide variety of music data formats
3. **Future-Proofing**: Easy to extend for new data formats or entity types
4. **Consistency**: Unified parameter patterns and error handling
5. **Maintainability**: Less code to maintain and test

## Usage Examples

### Example 1: Adding an artist from text

```json
{
  "function": "parse_and_store_music_data",
  "parameters": {
    "data": "The Beatles were an English rock band formed in Liverpool in 1960. The members were John Lennon, Paul McCartney, George Harrison and Ringo Starr.",
    "format_hint": "text"
  }
}
```

### Example 2: Adding an album with tracks from JSON

```json
{
  "function": "parse_and_store_music_data",
  "parameters": {
    "data": {
      "artist": "Taylor Swift",
      "album": "1989",
      "release_date": "2014-10-27",
      "tracks": [
        {"title": "Shake It Off", "duration_ms": 219200},
        {"title": "Blank Space", "duration_ms": 231827}
      ]
    },
    "format_hint": "json"
  }
}
```

### Example 3: Searching for entities

```json
{
  "function": "search_entities",
  "parameters": {
    "query": "taylor swift pop",
    "entity_types": ["Artist", "Album", "Track"],
    "max_results": 5
  }
}
```

## Implementation Timeline

1. **Week 1**: Implement universal parser and basic entity operations
2. **Week 2**: Implement relationship operations and unified search
3. **Week 3**: Integrate with server, testing, and documentation 