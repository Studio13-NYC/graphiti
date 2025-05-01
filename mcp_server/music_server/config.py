import os
import logging
import argparse
from collections.abc import Callable
from typing import Optional

from pydantic import BaseModel, Field

# Assuming graphiti_core and its dependencies are installed in the environment
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client import LLMClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_client import OpenAIClient
from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient

logger = logging.getLogger(__name__)

DEFAULT_LLM_MODEL = 'gpt-4o-mini' # Updated default for music
DEFAULT_EMBEDDER_MODEL = 'text-embedding-3-small'

class Neo4jConfig(BaseModel):
    """Configuration for Neo4j database connection."""
    uri: str = 'bolt://localhost:7687'
    user: str = 'neo4j'
    password: str = 'password'

    @classmethod
    def from_env(cls) -> 'Neo4jConfig':
        return cls(
            uri=os.environ.get('NEO4J_URI', 'bolt://localhost:7687'),
            user=os.environ.get('NEO4J_USER', 'neo4j'),
            password=os.environ.get('NEO4J_PASSWORD', 'password'),
        )

class GraphitiLLMConfig(BaseModel):
    """Configuration for the LLM client."""
    api_key: Optional[str] = None
    model: str = DEFAULT_LLM_MODEL
    temperature: float = 0.0

    @classmethod
    def from_env(cls) -> 'GraphitiLLMConfig':
        model_env = os.environ.get('MODEL_NAME', '')
        model = model_env if model_env.strip() else DEFAULT_LLM_MODEL
        
        return cls(
            api_key=os.environ.get('OPENAI_API_KEY'),
            model=model,
            temperature=float(os.environ.get('LLM_TEMPERATURE', '0.0')),
        )

    @classmethod
    def from_cli_and_env(cls, args: argparse.Namespace) -> 'GraphitiLLMConfig':
        config = cls.from_env()
        if hasattr(args, 'model') and args.model and args.model.strip():
            config.model = args.model
        if hasattr(args, 'temperature') and args.temperature is not None:
            config.temperature = args.temperature
        return config

    def create_client(self) -> Optional[LLMClient]:
        if self.api_key:
            # Standard OpenAI
            llm_config = LLMConfig(
                api_key=self.api_key,
                model=self.model,
                temperature=self.temperature
            )
            return OpenAIClient(config=llm_config)
        else:
            logger.warning('LLM client cannot be created: No API key found.')
            return None

    def create_cross_encoder_client(self) -> Optional[CrossEncoderClient]:
        if self.api_key:
            # Create a config specifically for the reranker
            llm_config = LLMConfig(api_key=self.api_key, model=self.model)
            return OpenAIRerankerClient(config=llm_config)
        return None

class GraphitiEmbedderConfig(BaseModel):
    """Configuration for the embedder client."""
    model: str = DEFAULT_EMBEDDER_MODEL
    api_key: Optional[str] = None

    @classmethod
    def from_env(cls) -> 'GraphitiEmbedderConfig':
        model_env = os.environ.get('EMBEDDER_MODEL_NAME', '')
        model = model_env if model_env.strip() else DEFAULT_EMBEDDER_MODEL
        
        return cls(
            model=model,
            api_key=os.environ.get('OPENAI_API_KEY'),
        )

    @classmethod
    def from_cli_and_env(cls, args: argparse.Namespace) -> 'GraphitiEmbedderConfig':
        config = cls.from_env()
        if hasattr(args, 'embedder_model') and args.embedder_model and args.embedder_model.strip():
            config.model = args.embedder_model
        return config

    def create_client(self) -> Optional[EmbedderClient]:
        if self.api_key:
            # Standard OpenAI Embeddings
            embedder_config = OpenAIEmbedderConfig(api_key=self.api_key, model=self.model)
            return OpenAIEmbedder(config=embedder_config)
        else:
            logger.warning('Embedder client cannot be created: No API key.')
            return None

class GraphitiConfig(BaseModel):
    """Top-level configuration for the Graphiti MCP server."""
    llm: GraphitiLLMConfig = Field(default_factory=GraphitiLLMConfig.from_env)
    embedder: GraphitiEmbedderConfig = Field(default_factory=GraphitiEmbedderConfig.from_env)
    neo4j: Neo4jConfig = Field(default_factory=Neo4jConfig.from_env)
    group_id: Optional[str] = None
    use_custom_entities: bool = False
    destroy_graph: bool = False
    entity_types: dict = {}  # Used for custom entity extraction

    @classmethod
    def from_cli_and_env(cls, args: argparse.Namespace) -> 'GraphitiConfig':
        config = cls() # Initializes with .from_env factories

        # Update LLM config from CLI
        config.llm = GraphitiLLMConfig.from_cli_and_env(args)
        
        # Update Embedder config from CLI
        config.embedder = GraphitiEmbedderConfig.from_cli_and_env(args)

        # Apply general CLI overrides
        if hasattr(args, 'group_id') and args.group_id:
            config.group_id = args.group_id
        if hasattr(args, 'use_custom_entities'):
            config.use_custom_entities = args.use_custom_entities
        if hasattr(args, 'destroy_graph'):
            config.destroy_graph = args.destroy_graph

        return config

class MCPConfig(BaseModel):
    """Configuration specific to the MCP server transport."""
    transport: str = 'sse'
    port: int = 8000

    @classmethod
    def from_cli(cls, args: argparse.Namespace) -> 'MCPConfig':
        config = cls()
        if hasattr(args, 'transport') and args.transport:
            config.transport = args.transport
        if hasattr(args, 'port') and args.port:
            config.port = args.port
        return config 