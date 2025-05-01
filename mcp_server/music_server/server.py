import asyncio
import logging
import os
import argparse
import sys
from dotenv import load_dotenv
from datetime import datetime, timezone

# Add the parent directory to the path to allow imports when run directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Try absolute imports first, then fall back to relative imports
try:
    from mcp.server.fastmcp import FastMCP
    from graphiti_core import Graphiti
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    from graphiti_core.llm_client.openai_client import OpenAIClient
    from graphiti_core.llm_client.config import LLMConfig
    # Neontology imports
    from neontology import init_neontology, Neo4jConfig

    # Import configuration and tools
    from mcp_server.music_server.config import GraphitiConfig, MCPConfig
    from mcp_server.music_server.tools import register_tools
    # Import the original tools (will be commented out but kept for reference)
    from mcp_server.music_server.music_tools import register_music_tools
    from mcp_server.music_server.music_tools_part2 import register_music_tools_part2
    from mcp_server.music_server.relationship_tools import register_relationship_tools
    # Import the new universal parser
    from mcp_server.music_server.parser import MusicDataParser
    from mcp_server.music_server.models.music import (
        Artist, Album, Track, Equipment, Studio, Person, 
        Credit, Label, Performance, Effect,
        Requirement, Preference, Procedure
    )
except ImportError:
    # If absolute imports fail, try relative imports
    from mcp.server.fastmcp import FastMCP
    from graphiti_core import Graphiti
    from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
    from graphiti_core.llm_client.openai_client import OpenAIClient
    from graphiti_core.llm_client.config import LLMConfig
    # Neontology imports
    from neontology import init_neontology, Neo4jConfig

    # Import configuration and tools using relative paths
    from .config import GraphitiConfig, MCPConfig
    from .tools import register_tools
    # Import the original tools (will be commented out but kept for reference)
    from .music_tools import register_music_tools
    from .music_tools_part2 import register_music_tools_part2
    from .relationship_tools import register_relationship_tools
    # Import the new universal parser
    from .parser import MusicDataParser
    from .models.music import (
        Artist, Album, Track, Equipment, Studio, Person, 
        Credit, Label, Performance, Effect,
        Requirement, Preference, Procedure
    )

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variables
graphiti_client = None
config = None
llm_client = None  # Add LLM client for parser

# Dictionary mapping entity type names to their Pydantic models
MUSIC_ENTITY_TYPES = {
    # Base Types (Optional)
    'Requirement': Requirement,
    'Preference': Preference,
    'Procedure': Procedure,
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

async def initialize_graphiti(cfg: GraphitiConfig):
    """Initialize the Graphiti client with the provided configuration."""
    global graphiti_client, llm_client
    
    try:
        # Create OpenAI clients for LLM and embedder
        llm_config = LLMConfig(
            api_key=cfg.llm.api_key,
            model=cfg.llm.model,
            temperature=cfg.llm.temperature
        )
        llm_client = OpenAIClient(config=llm_config)
        
        embedder_config = OpenAIEmbedderConfig(
            api_key=cfg.embedder.api_key,
            model=cfg.embedder.model
        )
        embedder = OpenAIEmbedder(config=embedder_config)
        
        # Initialize Graphiti client
        graphiti_client = Graphiti(
            uri=cfg.neo4j.uri,
            user=cfg.neo4j.user,
            password=cfg.neo4j.password,
            llm_client=llm_client,
            embedder=embedder,
        )
        
        # Build necessary indices and constraints
        await graphiti_client.build_indices_and_constraints()
        logger.info("Graphiti client initialized successfully")
        
        # Initialize Neontology
        logger.info("Initializing Neontology...")
        neo_config = Neo4jConfig(
            uri=cfg.neo4j.uri,
            username=cfg.neo4j.user,
            password=cfg.neo4j.password,
            database=cfg.neo4j.database if hasattr(cfg.neo4j, 'database') else None # Optional: Use database if specified in config
        )
        init_neontology(neo_config)
        logger.info("Neontology initialized successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize Graphiti or Neontology: {e}")
        raise

async def main():
    """Main entry point for the Music MCP Server."""
    global config, graphiti_client, llm_client
    
    # Load environment variables
    load_dotenv()
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Graphiti Music MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio", help="Transport protocol (stdio or SSE)")
    parser.add_argument("--group-id", type=str, default="music", help="Default group ID for entities")
    parser.add_argument("--model", type=str, help="OpenAI model to use")
    parser.add_argument("--embedder-model", type=str, help="OpenAI embedding model to use")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE transport")
    parser.add_argument("--use-custom-entities", action="store_true", help="Enable custom entity extraction")
    args = parser.parse_args()
    
    # Create configurations
    config = GraphitiConfig.from_cli_and_env(args)
    mcp_config = MCPConfig.from_cli(args)
    
    # Initialize Graphiti
    await initialize_graphiti(config)
    
    # Create MCP server
    mcp = FastMCP('graphiti-music', instructions='Graphiti Music Knowledge Graph MCP Server')
    
    # Register base tools
    register_tools(mcp, graphiti_client, config)
    
    # Register music-specific tools if custom entities are enabled
    if args.use_custom_entities:
        logger.info("Registering music entity tools with custom entity extraction")
        # Make entity types available for extraction
        config.use_custom_entities = True
        config.entity_types = MUSIC_ENTITY_TYPES
        
        # Always register original tools when custom entities are enabled
        logger.info("Using original separate tools for music entities")
        register_music_tools(mcp, config)
        register_music_tools_part2(mcp, graphiti_client)
        register_relationship_tools(mcp, graphiti_client)
    else:
        logger.info("Registering base tools only (custom entities disabled)")
        config.use_custom_entities = False
        config.entity_types = {}

    # Run the server
    logger.info(f"Starting Music MCP server with {mcp_config.transport} transport")
    if mcp_config.transport == "stdio":
        await mcp.run_stdio_async()
    elif mcp_config.transport == "sse":
        # Configure SSE settings
        mcp.settings.port = args.port
        # Add a small delay to potentially mitigate startup race conditions
        logger.info("Adding small delay before starting SSE server loop...")
        await asyncio.sleep(0.1) 
        # Run the SSE server
        await mcp.run_sse_async()

if __name__ == "__main__":
    asyncio.run(main()) 