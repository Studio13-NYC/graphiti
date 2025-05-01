import asyncio
import logging
import os
import argparse
import sys
from dotenv import load_dotenv

from mcp.server.fastmcp import FastMCP
from graphiti_core import Graphiti
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.llm_client.config import LLMConfig

# Import configuration and tools
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
        
    except Exception as e:
        logger.error(f"Failed to initialize Graphiti: {e}")
        raise

# Function to register the new streamlined tools
def register_streamlined_tools(mcp: FastMCP, graphiti_client: Graphiti, llm_client: OpenAIClient):
    """Register the streamlined universal parser tool"""
    logger.info("Registering streamlined music tools")
    
    @mcp.tool()
    async def parse_and_store_music_data(
        data: str,
        format_hint: str = None,
        extract_relationships: bool = True,
        dedup_strategy: str = "update_if_exists",
        group_id: str = None
    ):
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
        if not graphiti_client:
            return {"error": "Graphiti client not initialized"}
        
        try:
            # Use the universal parser
            effective_group_id = group_id or "music"
            parser = MusicDataParser(graphiti_client, llm_client)
            
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
    
    # Add entity management tools
    @mcp.tool()
    async def add_entity(
        entity_type: str,
        attributes: dict,
        group_id: str = None
    ):
        """
        Add a new entity of the specified type to the knowledge graph.
        
        Parameters:
        - entity_type: The type of entity to create (Artist, Album, Track, etc.)
        - attributes: Dictionary of entity attributes
        - group_id: Optional group ID for storing the entity
        """
        if not graphiti_client:
            return {"error": "Graphiti client not initialized"}
        
        try:
            if entity_type not in MUSIC_ENTITY_TYPES:
                return {"error": f"Unknown entity type: {entity_type}"}
            
            # Create entity model
            model_class = MUSIC_ENTITY_TYPES[entity_type]
            
            # Filter attributes to include only fields in the model
            valid_fields = set(model_class.__fields__.keys())
            filtered_attributes = {k: v for k, v in attributes.items() if k in valid_fields}
            
            # Create episode body
            episode_body = {entity_type: filtered_attributes}
            
            # Add as JSON episode
            effective_group_id = group_id or "music"
            result = await graphiti_client.add_episode(
                name=f"{entity_type}: {filtered_attributes.get('name') or filtered_attributes.get('title')}",
                episode_body=episode_body,
                source="json",
                group_id=effective_group_id,
                entity_types={entity_type: model_class}
            )
            
            # Extract the created entity node
            created_nodes = [node for node in result.nodes if entity_type in node.labels]
            if not created_nodes:
                return {"error": f"{entity_type} creation failed: no node found in result"}
            
            node = created_nodes[0]
            return {
                "uuid": str(node.uuid),
                "entity_type": entity_type,
                "attributes": node.attributes,
                "created_at": node.created_at.isoformat() if node.created_at else None,
                "group_id": node.group_id
            }
        except Exception as e:
            logger.error(f"Error creating {entity_type}: {e}")
            return {"error": f"{entity_type} creation failed: {str(e)}"}
    
    @mcp.tool()
    async def update_entity(
        uuid: str,
        attributes: dict
    ):
        """
        Update an existing entity's attributes.
        
        Parameters:
        - uuid: Entity UUID
        - attributes: Dictionary of attributes to update
        """
        if not graphiti_client:
            return {"error": "Graphiti client not initialized"}
        
        try:
            # Get current entity to ensure it exists
            entity = await graphiti_client.get_entity_node(uuid)
            if not entity:
                return {"error": "Entity not found"}
            
            # Update the entity
            updated_entity = await graphiti_client.update_entity_node(uuid, attributes)
            
            # Format response
            entity_type = "Entity"
            if len(updated_entity.labels) > 1:
                # Get the most specific label (not 'Entity')
                entity_type = [label for label in updated_entity.labels if label != "Entity"][0]
                
            return {
                "uuid": str(updated_entity.uuid),
                "entity_type": entity_type,
                "attributes": updated_entity.attributes,
                "created_at": updated_entity.created_at.isoformat() if updated_entity.created_at else None,
                "group_id": updated_entity.group_id
            }
        except Exception as e:
            logger.error(f"Error updating entity: {e}")
            return {"error": f"Failed to update entity: {str(e)}"}
    
    @mcp.tool()
    async def delete_entity(
        uuid: str
    ):
        """
        Delete an entity from the knowledge graph.
        
        Parameters:
        - uuid: Entity UUID
        """
        if not graphiti_client:
            return {"error": "Graphiti client not initialized"}
        
        try:
            # Get current entity to ensure it exists
            entity = await graphiti_client.get_entity_node(uuid)
            if not entity:
                return {"error": "Entity not found"}
            
            # Delete the entity
            await graphiti_client.delete_entity_node(uuid)
            
            return {"message": f"Entity {uuid} deleted successfully"}
        except Exception as e:
            logger.error(f"Error deleting entity: {e}")
            return {"error": f"Failed to delete entity: {str(e)}"}
    
    @mcp.tool()
    async def get_entity(
        uuid: str
    ):
        """
        Retrieve an entity by UUID.
        
        Parameters:
        - uuid: Entity UUID
        """
        if not graphiti_client:
            return {"error": "Graphiti client not initialized"}
        
        try:
            entity = await graphiti_client.get_entity_node(uuid)
            if not entity:
                return {"error": "Entity not found"}
            
            # Format response
            entity_type = "Entity"
            if len(entity.labels) > 1:
                # Get the most specific label (not 'Entity')
                entity_type = [label for label in entity.labels if label != "Entity"][0]
                
            return {
                "uuid": str(entity.uuid),
                "entity_type": entity_type,
                "attributes": entity.attributes,
                "created_at": entity.created_at.isoformat() if entity.created_at else None,
                "group_id": entity.group_id
            }
        except Exception as e:
            logger.error(f"Error retrieving entity: {e}")
            return {"error": f"Failed to retrieve entity: {str(e)}"}
    
    @mcp.tool()
    async def create_relationship(
        source_uuid: str,
        target_uuid: str,
        relationship_type: str,
        attributes: dict = None,
        group_id: str = None
    ):
        """
        Create a relationship between two entities.
        
        Parameters:
        - source_uuid: Source entity UUID
        - target_uuid: Target entity UUID
        - relationship_type: Type of relationship (e.g., "PERFORMED_ON", "CONTAINS_TRACK")
        - attributes: Optional attributes for the relationship
        - group_id: Optional group ID
        """
        if not graphiti_client:
            return {"error": "Graphiti client not initialized"}
        
        try:
            # Verify that both entities exist
            source_entity = await graphiti_client.get_entity_node(source_uuid)
            if not source_entity:
                return {"error": f"Source entity {source_uuid} not found"}
                
            target_entity = await graphiti_client.get_entity_node(target_uuid)
            if not target_entity:
                return {"error": f"Target entity {target_uuid} not found"}
            
            # Create the relationship
            effective_group_id = group_id or "music"
            edge = await graphiti_client.create_entity_edge(
                source_node_uuid=source_uuid,
                target_node_uuid=target_uuid,
                relationship_type=relationship_type,
                attributes=attributes or {},
                group_id=effective_group_id
            )
            
            return {
                "uuid": str(edge.uuid),
                "source_uuid": str(edge.source_node_uuid),
                "target_uuid": str(edge.target_node_uuid),
                "relationship_type": edge.relationship_type,
                "attributes": edge.attributes,
                "created_at": edge.created_at.isoformat() if edge.created_at else None,
                "group_id": edge.group_id
            }
        except Exception as e:
            logger.error(f"Error creating relationship: {e}")
            return {"error": f"Failed to create relationship: {str(e)}"}
    
    @mcp.tool()
    async def get_relationships(
        entity_uuid: str,
        relationship_type: str = None,
        direction: str = "both",
        entity_types: list = None,
        group_ids: list = None
    ):
        """
        Get relationships for an entity, with optional filtering.
        
        Parameters:
        - entity_uuid: Entity UUID
        - relationship_type: Optional relationship type filter
        - direction: "incoming", "outgoing", or "both"
        - entity_types: Optional list of entity types to filter related entities
        - group_ids: Optional group IDs to search within
        """
        if not graphiti_client:
            return {"error": "Graphiti client not initialized"}
        
        try:
            # Verify entity exists
            entity = await graphiti_client.get_entity_node(entity_uuid)
            if not entity:
                return {"error": f"Entity {entity_uuid} not found"}
            
            # Construct cypher query based on parameters
            cypher_query = ""
            params = {"entity_uuid": entity_uuid}
            
            if direction == "outgoing":
                cypher_query = """
                MATCH (n)-[r]->(m)
                WHERE id(n) = $entity_uuid
                """
            elif direction == "incoming":
                cypher_query = """
                MATCH (n)<-[r]-(m)
                WHERE id(n) = $entity_uuid
                """
            else:  # both
                cypher_query = """
                MATCH (n)-[r]-(m)
                WHERE id(n) = $entity_uuid
                """
            
            # Add relationship type filter if provided
            if relationship_type:
                cypher_query += f"AND type(r) = $rel_type\n"
                params["rel_type"] = relationship_type
            
            # Add entity type filter if provided
            if entity_types and len(entity_types) > 0:
                type_conditions = []
                for i, entity_type in enumerate(entity_types):
                    type_conditions.append(f"$entity_type_{i} in labels(m)")
                    params[f"entity_type_{i}"] = entity_type
                
                cypher_query += f"AND ({' OR '.join(type_conditions)})\n"
            
            # Add group filter if provided
            if group_ids and len(group_ids) > 0:
                group_conditions = []
                for i, group_id in enumerate(group_ids):
                    group_conditions.append(f"m.group_id = $group_id_{i}")
                    params[f"group_id_{i}"] = group_id
                
                cypher_query += f"AND ({' OR '.join(group_conditions)})\n"
            
            # Complete the query
            cypher_query += "RETURN r, m"
            
            # Execute query
            result = await graphiti_client.run_cypher(cypher_query, params)
            
            # Format results
            relationships = []
            for record in result:
                edge = record["r"]
                related_node = record["m"]
                
                # Get related entity type
                related_entity_type = "Entity"
                if len(related_node["labels"]) > 1:
                    related_entity_type = [label for label in related_node["labels"] if label != "Entity"][0]
                
                relationships.append({
                    "relationship": {
                        "uuid": str(edge["uuid"]),
                        "source_uuid": str(edge["source_node_uuid"]),
                        "target_uuid": str(edge["target_node_uuid"]),
                        "relationship_type": edge["relationship_type"],
                        "attributes": edge["attributes"],
                        "created_at": edge["created_at"].isoformat() if edge.get("created_at") else None,
                        "group_id": edge["group_id"]
                    },
                    "related_entity": {
                        "uuid": str(related_node["uuid"]),
                        "entity_type": related_entity_type,
                        "attributes": related_node["attributes"],
                        "created_at": related_node["created_at"].isoformat() if related_node.get("created_at") else None,
                        "group_id": related_node["group_id"]
                    }
                })
            
            return {
                "message": f"Found {len(relationships)} relationships for entity {entity_uuid}",
                "relationships": relationships
            }
        except Exception as e:
            logger.error(f"Error getting relationships: {e}")
            return {"error": f"Failed to get relationships: {str(e)}"}
    
    @mcp.tool()
    async def search_entities(
        query: str,
        entity_types: list = None,
        group_ids: list = None,
        max_results: int = 10,
        center_entity_uuid: str = None
    ):
        """
        Search for entities matching a query.
        
        Parameters:
        - query: Search query
        - entity_types: Optional list of entity types to search for
        - group_ids: Optional group IDs to search within
        - max_results: Maximum number of results to return
        - center_entity_uuid: Optional UUID to prioritize entities connected to this one
        """
        if not graphiti_client:
            return {"error": "Graphiti client not initialized"}
        
        try:
            from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF
            from graphiti_core.search.search_filters import SearchFilters
            
            # Set up search filters
            filters = None
            if entity_types and len(entity_types) > 0:
                filters = SearchFilters(node_labels=entity_types)
            
            # Execute search
            effective_group_ids = group_ids or ["music"]
            search_results = await graphiti_client._search(
                query=query,
                group_ids=effective_group_ids,
                search_config=NODE_HYBRID_SEARCH_RRF,
                search_filters=filters,
                limit=max_results
            )
            
            # Format results
            entities = []
            for node in search_results.nodes:
                entity_type = "Entity"
                if len(node.labels) > 1:
                    entity_type = [label for label in node.labels if label != "Entity"][0]
                
                entities.append({
                    "uuid": str(node.uuid),
                    "entity_type": entity_type,
                    "attributes": node.attributes,
                    "created_at": node.created_at.isoformat() if node.created_at else None,
                    "group_id": node.group_id,
                    "search_score": node.search_score
                })
            
            return {
                "message": f"Found {len(entities)} entities matching query '{query}'",
                "entities": entities
            }
        except Exception as e:
            logger.error(f"Error searching entities: {e}")
            return {"error": f"Failed to search entities: {str(e)}"}

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
    parser.add_argument("--use-streamlined", action="store_true", help="Use streamlined universal parser tools")
    args = parser.parse_args()
    
    # Create configurations
    config = GraphitiConfig.from_cli_and_env(args)
    mcp_config = MCPConfig.from_cli(args)
    
    # Initialize Graphiti
    await initialize_graphiti(config)
    
    # Create MCP server
    mcp = FastMCP('graphiti-music', instructions='Graphiti Music Knowledge Graph MCP Server')
    
    # Register tools
    register_tools(mcp, graphiti_client, config)
    
    # Register music-specific tools
    if args.use_custom_entities:
        logger.info("Registering music entity tools with custom entity extraction")
        # Make entity types available for extraction
        config.use_custom_entities = True
        config.entity_types = MUSIC_ENTITY_TYPES
    else:
        logger.info("Registering music entity tools without custom entity extraction")
        config.use_custom_entities = False
        config.entity_types = {}
    
    if args.use_streamlined:
        # Register the new streamlined tools
        logger.info("Using streamlined universal parser tools")
        register_streamlined_tools(mcp, graphiti_client, llm_client)
    else:
        # Register original tools (for backward compatibility)
        logger.info("Using original separate tools")
        register_music_tools(mcp, graphiti_client)
        register_music_tools_part2(mcp, graphiti_client)
        register_relationship_tools(mcp, graphiti_client)
    
    # Run the server
    logger.info(f"Starting Music MCP server with {mcp_config.transport} transport")
    if mcp_config.transport == "stdio":
        await mcp.run_stdio_async()
    elif mcp_config.transport == "sse":
        # Configure SSE settings
        mcp.settings.port = args.port
        # Run the SSE server
        await mcp.run_sse_async()

if __name__ == "__main__":
    asyncio.run(main()) 