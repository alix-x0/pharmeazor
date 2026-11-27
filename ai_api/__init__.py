"""
Pharmeazor AI API Package
=========================
Intelligent Pharmaceutical RAG Architecture:
- Retrieval: Clinical section-aware chunking, BGE-M3 embeddings, Qdrant hybrid retrieval
- Augmentation: Clinical Knowledge Graph, Ontology, and Subgraph Augmentation
- Generation: Baseline and Context-Enriched Groq LLM Generation
"""

# Chunking Exports
from ai_api.rag.chunking import (
    DEFAULT_DATA_DIR,
    DEFAULT_PROCESSED_DIR,
    ChunkingConfig,
    DrugChunk,
    DrugChunker,
    RecursiveSemanticSplitter,
    build_context_header,
    categorize_section,
    chunk_corpus,
    chunk_document,
    chunk_file,
    chunk_processed_corpus,
    default_chunker,
    get_all_dossiers,
)

# Embedding & Vector Store Exports
from ai_api.rag.embedding import (
    BGEM3Embedder,
    EmbeddingConfig,
    EmbeddingOutput,
    default_embedder,
    embed_query,
    embed_texts,
)
from ai_api.rag.vector_store import (
    QdrantConfig,
    QdrantVectorStore,
    chunk_id_to_uuid,
    default_store,
)
from ai_api.rag.retriever import (
    DrugRAGPipeline,
    IndexingStats,
    RetrievalResult,
    default_pipeline,
    index_pharmaceutical_corpus,
    search_drugs,
)

# Knowledge Graph & Ontology Exports
from ai_api.Augmentation.knowledge_graph.ontology import (
    EntityType,
    KGEntity,
    KGRelation,
    RelationType,
)

__all__ = [
    # Chunking
    "DEFAULT_DATA_DIR",
    "DEFAULT_PROCESSED_DIR",
    "DrugChunk",
    "DrugChunker",
    "ChunkingConfig",
    "RecursiveSemanticSplitter",
    "build_context_header",
    "categorize_section",
    "chunk_corpus",
    "chunk_document",
    "chunk_file",
    "chunk_processed_corpus",
    "default_chunker",
    "get_all_dossiers",
    # Embedding
    "BGEM3Embedder",
    "EmbeddingConfig",
    "EmbeddingOutput",
    "default_embedder",
    "embed_texts",
    "embed_query",
    # Vector Store
    "QdrantConfig",
    "QdrantVectorStore",
    "chunk_id_to_uuid",
    "default_store",
    # Retriever
    "DrugRAGPipeline",
    "IndexingStats",
    "RetrievalResult",
    "default_pipeline",
    "index_pharmaceutical_corpus",
    "search_drugs",
    # Knowledge Graph Ontology
    "EntityType",
    "RelationType",
    "KGEntity",
    "KGRelation",
]
