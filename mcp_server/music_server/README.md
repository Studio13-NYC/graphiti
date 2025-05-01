# Graphiti Music Knowledge Graph MCP Server

## Overview

This MCP server provides tools for creating and querying a music knowledge graph within the Graphiti system. It enables you to store structured information about music entities such as artists, albums, tracks, studios, equipment, and more.

## Features

- Universal music data parser that works with various formats (text, JSON, Spotify API responses)
- Automatic relationship inference between entities (e.g., artist -> album -> tracks)
- Entity search across the knowledge graph
- Comprehensive relationship management

## Available Tools

This server offers two tool sets:

1. **Streamlined Universal Tools**: A simplified set of tools centered around a universal parser (default)
2. **Individual Entity Tools**: A more extensive set of entity-specific tools (legacy mode)

### Streamlined Universal Tools

This modern toolset provides a simplified interface with full functionality:

#### Core Tool: Universal Parser

```python
parse_and_store_music_data(
    data: str,
    format_hint: Optional[str] = None,
    extract_relationships: bool = True,
    dedup_strategy: str = "update_if_exists",
    group_id: Optional[str] = None
)
```

This powerful tool can extract multiple music entities from text, JSON, or API responses. Example inputs:

- **Text**: "Bohemian Rhapsody was recorded by Queen in 1975 for their album A Night at the Opera."
- **JSON**: `{"artist": "Taylor Swift", "album": "1989", "tracks": ["Shake It Off", "Blank Space"]}`
- **Spotify API**: Spotify album object with tracks information

#### Additional Tools

- **Entity Tools**: `add_entity`, `update_entity`, `delete_entity`, `get_entity`  
- **Relationship Tools**: `create_relationship`, `get_relationships`
- **Search Tools**: `search_entities`

### Individual Entity Tools (Legacy)

The server also maintains a more extensive set of entity-specific tools for backward compatibility:

- **Artist Tools**: `add_artist`, `update_artist`, `delete_artist`, `get_artist`, `search_artists`
- **Album Tools**: `add_album`, `update_album`, `delete_album`, `get_album`, `search_albums`
- **Track Tools**: `add_track`, `update_track`, `delete_track`, `get_track`, `search_tracks`
- **And more for each entity type**

## Setup and Usage

### Prerequisites

- Python 3.10+
- Neo4j database
- OpenAI API key

### Running the Server

1. Set environment variables for Neo4j and OpenAI
   ```bash
   export OPENAI_API_KEY='your-openai-key'
   export NEO4J_URI='bolt://localhost:7687'
   export NEO4J_USER='neo4j'
   export NEO4J_PASSWORD='your-password'
   ```

2. Run using the provided script
   ```bash
   ./run_music_server_sse.sh
   ```

This will start the server with the streamlined tools by default.

### Optional Flags

- `--use-streamlined`: Use the streamlined universal parser tools (default in script)
- `--use-custom-entities`: Enable custom entity extraction
- `--transport`: Specify transport protocol (`stdio` or `sse`)
- `--port`: Specify port for SSE transport (default: 8000)
- `--model`: Specify OpenAI model
- `--embedder-model`: Specify OpenAI embedding model

## Example Usage

### Using the Universal Parser

```json
{
  "function": "parse_and_store_music_data",
  "parameters": {
    "data": "The Beatles recorded Abbey Road in 1969, featuring the hit songs 'Come Together' and 'Here Comes the Sun'.",
    "format_hint": "text"
  }
}
```

The parser will extract:
- Artist: The Beatles
- Album: Abbey Road
- Tracks: Come Together, Here Comes the Sun
- Relationships between these entities

### Universal JSON Format Example

```json
{
  "function": "parse_and_store_music_data",
  "parameters": {
    "data": {
      "artist": {
        "name": "Pink Floyd",
        "country": "UK",
        "genres": ["Progressive Rock", "Psychedelic Rock"]
      },
      "album": {
        "title": "The Dark Side of the Moon",
        "release_date": "1973-03-01",
        "total_tracks": 10
      },
      "tracks": [
        {"title": "Speak to Me", "duration_ms": 90000},
        {"title": "Breathe", "duration_ms": 170000},
        {"title": "Time", "duration_ms": 421000}
      ]
    },
    "format_hint": "json"
  }
}
```

## Entity Types

The server supports the following entity types:

- `Artist`: Musicians or bands
- `Album`: Collections of tracks
- `Track`: Individual songs
- `Equipment`: Musical instruments and gear
- `Studio`: Recording facilities
- `Person`: Producers, engineers, etc.
- `Credit`: Attribution for contributions
- `Label`: Record labels and publishers
- `Performance`: Live performances and concerts
- `Effect`: Audio effects used in production

## Music Entity Models

The server supports the following music entity types:

- **Artist** - Musical performers/creators
- **Album** - Collections of tracks
- **Track** - Individual songs
- **Equipment** - Instruments/gear
- **Studio** - Recording facilities
- **Person** - Production personnel
- **Credit** - Attribution roles
- **Label** - Music companies
- **Performance** - Live events
- **Effect** - Audio processing

Each entity type has a corresponding Pydantic model with all required fields and optional metadata fields, designed to be fully extensible for future needs.

## Available Tools

### Entity Management Tools

Each music entity type (Artist, Album, Track, etc.) has the following operations:
- **add_[entity]** - Create a new entity (e.g., `add_artist`, `add_album`, `add_track`)
- **get_[entity]** - Retrieve an entity by UUID
- **search_[entity]s** - Search entities by query
- **update_[entity]** - Update an existing entity
- **delete_[entity]** - Remove an entity

### Relationship Management Tools

The server supports creating, querying, updating, and deleting relationships between entities:

- **add_track_to_album** - Link a track to an album
- **assign_artist_to_track** - Link an artist to a track
- **assign_label_to_album** - Link a label to an album
- **record_track_at_studio** - Link a track to a recording studio
- **add_equipment_to_track** - Associate equipment with a track
- **assign_person_to_track** - Credit a person on a track
- **link_artist_album** - Associate an artist with an album
- **add_effect_to_track** - Associate an effect with a track

### Query Relationship Tools

- **get_album_tracks** - Get all tracks on an album
- **get_artist_tracks** - Get all tracks by an artist
- **get_relationships** - Get all relationships for an entity

### Knowledge Enrichment Tools

- **find_similar_tracks** - Find tracks similar to a given track
- **get_artist_collaborators** - Find artists who have collaborated with a given artist

### Generic Tools

- **create_relationship** - Create any type of relationship between entities
- **update_relationship** - Update relationship attributes
- **delete_relationship** - Remove a relationship

## Temporal Awareness

All entities and relationships in the graph maintain temporal metadata, tracking when they were created, modified, or deprecated. This enables:

- Point-in-time queries to see the state of the music graph at any moment
- Tracking the evolution of artists, albums, and tracks over time
- Historical analysis of music production and relationships

## Schema Evolution

The system is designed for schema evolution:
- All entity models use optional fields (where appropriate) to allow partial data
- Each model includes a `schema_version` field to track compatibility
- New fields can be added to models without breaking existing data
- New entity types can be added to the ecosystem at any time

## Usage

### Starting the Server

Run the server with SSE transport and custom entity extraction:

```bash
./run_music_server_sse.sh
```

Or manually:

```bash
uv run server.py --transport sse --use-custom-entities --group-id music
```

### Configuration

Configure the server via environment variables in a `.env` file:

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
OPENAI_API_KEY=your_api_key
MODEL_NAME=gpt-4o-mini
EMBEDDER_MODEL_NAME=text-embedding-3-small
```

Or override via command line arguments:

```bash
uv run server.py --model gpt-4o --embedder-model text-embedding-3-large
```

## Examples

### Adding an Artist and Album

1. Add an artist:
```json
{
  "function": "add_artist", 
  "parameters": {
    "name": "The Beatles",
    "biography": "Iconic British rock band formed in Liverpool in 1960",
    "genres": "rock,pop",
    "country": "United Kingdom"
  }
}
```

2. Add an album:
```json
{
  "function": "add_album", 
  "parameters": {
    "title": "Abbey Road",
    "release_date": "1969-09-26",
    "album_type": "LP",
    "total_tracks": 17
  }
}
```

3. Link them:
```json
{
  "function": "link_artist_album", 
  "parameters": {
    "artist_uuid": "...",
    "album_uuid": "..."
  }
}
```

### Finding Relationships

```json
{
  "function": "get_album_tracks", 
  "parameters": {
    "album_uuid": "..."
  }
}
```

## Extending the System

To add new entity types or relationships:

1. Define a new Pydantic model in `models/music.py`
2. Add the model to `MUSIC_ENTITY_TYPES` in `server.py`
3. Create corresponding tools for the new entity type
4. Register the tools in the main server file 