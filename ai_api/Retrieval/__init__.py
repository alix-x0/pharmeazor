"""
Pharmeazor Retrieval Package
============================
Subsystem for Domain-Aware Pharmaceutical Retrieval & RAG:
- chunking.py: Clinical section-aware chunking engine
- embedding.py: BGE-M3 dense & sparse multilingual embedder
- vector_store.py: Qdrant vector database store manager
- retriever.py: Hybrid search (RRF) & indexing pipeline orchestrator
"""

from ai_api.Retrieval.chunking import (
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
    clean_text,
    default_chunker,
    generate_chunk_id,
    get_all_dossiers,
    normalize_section_key,
)
from ai_api.Retrieval.embedding import (
    BGEM3Embedder,
    EmbeddingConfig,
    EmbeddingOutput,
    default_embedder,
    embed_query,
    embed_texts,
)
from ai_api.Retrieval.retriever import (
    DrugRAGPipeline,
    IndexingStats,
    RetrievalResult,
    default_pipeline,
    index_pharmaceutical_corpus,
    search_drugs,
)
from ai_api.Retrieval.vector_store import (
    QdrantConfig,
    QdrantVectorStore,
    chunk_id_to_uuid,
    default_store,
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
    "clean_text",
    "generate_chunk_id",
    "get_all_dossiers",
    "normalize_section_key",
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
    # Retriever & Pipeline
    "DrugRAGPipeline",
    "RetrievalResult",
    "IndexingStats",
    "default_pipeline",
    "index_pharmaceutical_corpus",
    "search_drugs",
]
