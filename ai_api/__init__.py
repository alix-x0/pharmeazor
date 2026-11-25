"""
Pharmeazor AI API Package
=========================
Intelligent Pharmaceutical RAG subsystem:
- Clinical section-aware chunking engine
- Multilingual BGE-M3 dense & sparse embedding engine
- Qdrant Vector Database hybrid indexing and retrieval
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
    default_chunker,
    get_all_dossiers,
)
from ai_api.Retrieval.embedding import (
    BGEM3Embedder,
    DrugRAGPipeline,
    EmbeddingConfig,
    EmbeddingOutput,
    IndexingStats,
    QdrantConfig,
    QdrantVectorStore,
    RetrievalResult,
    chunk_id_to_uuid,
    default_embedder,
    default_pipeline,
    default_store,
    embed_query,
    embed_texts,
    index_pharmaceutical_corpus,
    search_drugs,
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
    # Embedding & Qdrant
    "BGEM3Embedder",
    "EmbeddingConfig",
    "EmbeddingOutput",
    "QdrantConfig",
    "QdrantVectorStore",
    "DrugRAGPipeline",
    "RetrievalResult",
    "IndexingStats",
    "chunk_id_to_uuid",
    "default_embedder",
    "default_store",
    "default_pipeline",
    "embed_texts",
    "embed_query",
    "index_pharmaceutical_corpus",
    "search_drugs",
]
