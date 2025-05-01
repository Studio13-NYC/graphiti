"""
Test script for the universal music data parser.

This script tests various input formats and validates that the parser correctly
extracts entities and creates relationships.

Usage:
    python test_universal_parser.py
"""

import asyncio
import json
import os
import logging
from dotenv import load_dotenv

from graphiti_core import Graphiti
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.embedder.openai import OpenAIEmbedder

from parser import MusicDataParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test data for different formats
TEXT_DATA = """
Queen recorded the album 'A Night at the Opera' in 1975, which featured the hit song 'Bohemian Rhapsody'.
Freddie Mercury was the lead vocalist of Queen. The album was released by EMI Records.
"""

JSON_DATA = {
    "artist": {
        "name": "Taylor Swift",
        "genres": ["Pop", "Country"],
        "country": "USA"
    },
    "album": {
        "title": "1989",
        "release_date": "2014-10-27",
        "album_type": "album"
    },
    "tracks": [
        {"title": "Shake It Off", "duration_ms": 219200},
        {"title": "Blank Space", "duration_ms": 231827},
        {"title": "Style", "duration_ms": 231000}
    ]
}

SPOTIFY_LIKE_DATA = {
    "type": "album",
    "name": "Back in Black",
    "artists": [
        {
            "type": "artist",
            "name": "AC/DC",
            "external_urls": {
                "spotify": "https://open.spotify.com/artist/711MCceyCBcFnzjGY4Q7Un"
            }
        }
    ],
    "release_date": "1980-07-25",
    "total_tracks": 10,
    "tracks": {
        "items": [
            {
                "type": "track",
                "name": "Hells Bells",
                "duration_ms": 312000,
                "explicit": False,
                "artists": [
                    {
                        "name": "AC/DC",
                        "type": "artist"
                    }
                ]
            },
            {
                "type": "track",
                "name": "Back in Black",
                "duration_ms": 255000,
                "explicit": False
            }
        ]
    }
}

async def test_universal_parser():
    """Test the universal parser with different data formats."""
    # Load environment variables
    load_dotenv()
    
    # Create LLM and Embedder clients
    llm_client = OpenAIClient(
        config={
            "api_key": os.getenv("OPENAI_API_KEY"),
            "model": os.getenv("OPENAI_MODEL", "gpt-4o")
        }
    )
    
    embedder = OpenAIEmbedder(
        config={
            "api_key": os.getenv("OPENAI_API_KEY"),
            "model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        }
    )
    
    # Initialize Graphiti client
    graphiti_client = Graphiti(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD", "password"),
        llm_client=llm_client,
        embedder=embedder,
    )
    
    # Create parser instance
    parser = MusicDataParser(graphiti_client, llm_client)
    
    # Test 1: Parse text data
    logger.info("Test 1: Testing text data parsing")
    text_result = await parser.parse_and_store(
        data=TEXT_DATA,
        format_hint="text",
        extract_relationships=True,
        group_id="test_text"
    )
    print(f"Text parsing result: {json.dumps(text_result, indent=2)}")
    
    # Test 2: Parse JSON data
    logger.info("Test 2: Testing JSON data parsing")
    json_result = await parser.parse_and_store(
        data=json.dumps(JSON_DATA),
        format_hint="json",
        extract_relationships=True,
        group_id="test_json"
    )
    print(f"JSON parsing result: {json.dumps(json_result, indent=2)}")
    
    # Test 3: Parse Spotify-like data
    logger.info("Test 3: Testing Spotify data parsing")
    spotify_result = await parser.parse_and_store(
        data=json.dumps(SPOTIFY_LIKE_DATA),
        format_hint="spotify",
        extract_relationships=True,
        group_id="test_spotify"
    )
    print(f"Spotify parsing result: {json.dumps(spotify_result, indent=2)}")
    
    # Clean up created entities (optional)
    # await cleanup_test_data(graphiti_client)
    
    logger.info("All tests completed!")

async def cleanup_test_data(graphiti_client):
    """Clean up test data created during tests."""
    # Delete test groups
    for group_id in ["test_text", "test_json", "test_spotify"]:
        cypher = "MATCH (n) WHERE n.group_id = $group_id DETACH DELETE n"
        await graphiti_client.run_cypher(cypher, {"group_id": group_id})
    
    logger.info("Cleaned up test data")

if __name__ == "__main__":
    asyncio.run(test_universal_parser()) 