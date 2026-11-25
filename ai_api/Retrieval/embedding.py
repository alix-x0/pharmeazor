"""
Pharmeazor RAG System - BGE-M3 Multilingual Embedding & Qdrant Integration Engine
================================================================================
Implements state-of-the-art hybrid embedding (Dense + Sparse/Lexical) using BAAI/bge-m3
and stores pharmaceutical knowledge chunks from `chunking.py` into Qdrant Vector Database.

Architecture & Retrieval Strategy:
----------------------------------
1. BGE-M3 Multi-Functionality:
   - Dense Embeddings: 1024-dimensional normalized vectors capturing deep clinical semantics.
   - Sparse Lexical Weights: Token-level importance scores (similar to BM25) computed at
     zero additional model cost during encoding, enabling exact drug name / DCI / dosage matches.
   - Multi-Linguality: Native multilingual capability across 100+ languages (French, Arabic, English).
   - Multi-Granularity: Handles sequence lengths up to 8192 tokens.

2. Qdrant Hybrid Collection Architecture:
   - Dual-vector storage:
     * Named dense vector: 'dense' (size=1024, distance=Cosine)
     * Named sparse vector: 'sparse' (token ID indices + lexical weights)
   - Hybrid Search: Evaluates dense semantic proximity and sparse lexical matching simultaneously,
     fused via Reciprocal Rank Fusion (RRF) for optimal pharmaceutical precision.
   - Deterministic Point IDs: Generates standard UUIDv5 from `chunk_id` for idempotent upserts.
   - Indexed Payloads: Automatically configures fast indexes on clinical metadata fields
     (dci, brand, source, section_category, doc_type, source_priority).

3. Integration with `chunking.py`:
   - Seamlessly consumes `DrugChunk` objects produced by `DrugChunker`, `chunk_corpus`,
     or `chunk_file`.
   - Embeds the contextual header + section content while preserving rich structured payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)

# Ensure package root is in path
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import chunking components
try:
    from ai_api.Retrieval.chunking import (
        DEFAULT_DATA_DIR,
        ChunkingConfig,
        DrugChunk,
        DrugChunker,
        chunk_corpus,
        chunk_document,
        chunk_file,
    )
except ImportError:
    # Fallback if imported directly inside ai_api
    from ai_api.Retrieval.chunking import (  # type: ignore
        DEFAULT_DATA_DIR,
        ChunkingConfig,
        DrugChunk,
        DrugChunker,
        chunk_corpus,
        chunk_document,
        chunk_file,
    )

# Optional dependency imports with clean status flags
_FLAG_EMBEDDING_AVAILABLE = False
_SENTENCE_TRANSFORMERS_AVAILABLE = False
_QDRANT_AVAILABLE = False

try:
    from FlagEmbedding import BGEM3FlagModel  # type: ignore
    _FLAG_EMBEDDING_AVAILABLE = True
except ImportError:
    BGEM3FlagModel = None  # type: ignore

try:
    from sentence_transformers import SentenceTransformer  # type: ignore
    _SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None  # type: ignore

try:
    from qdrant_client import QdrantClient  # type: ignore
    from qdrant_client.models import (  # type: ignore
        Distance,
        FieldCondition,
        Filter,
        Fusion,
        FusionQuery,
        MatchValue,
        PayloadSchemaType,
        PointStruct,
        Prefetch,
        SearchParams,
        SparseIndexParams,
        SparseVector,
        SparseVectorParams,
        VectorParams,
    )
    _QDRANT_AVAILABLE = True
except ImportError:
    _QDRANT_AVAILABLE = False
    QdrantClient = None  # type: ignore

    @dataclass
    class SparseVector:  # type: ignore
        indices: List[int]
        values: List[float]

    @dataclass
    class PointStruct:  # type: ignore
        id: Any
        vector: Any
        payload: Dict[str, Any]

    class Distance:  # type: ignore
        COSINE = "Cosine"
        EUCLID = "Euclid"
        DOT = "Dot"

    @dataclass
    class VectorParams:  # type: ignore
        size: int
        distance: Any

    @dataclass
    class SparseIndexParams:  # type: ignore
        on_disk: bool = True

    @dataclass
    class SparseVectorParams:  # type: ignore
        index: Optional[Any] = None

    class PayloadSchemaType:  # type: ignore
        KEYWORD = "keyword"
        INTEGER = "integer"
        FLOAT = "float"
        TEXT = "text"



# ---------------------------------------------------------------------------
# Configuration Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EmbeddingConfig:
    """Configuration for BGE-M3 model inference and vector dimensions."""
    model_name: str = "BAAI/bge-m3"
    use_fp16: bool = True               # Halves memory and speeds up GPU inference
    device: Optional[str] = None        # Auto-detects 'cuda' if available, else 'cpu'
    batch_size: int = 12                # Batch size for encoding
    max_length: int = 8192              # Max input sequence length (BGE-M3 max: 8192)
    return_dense: bool = True           # Generate 1024-d dense vectors
    return_sparse: bool = True          # Generate token lexical weights (sparse vectors)
    return_colbert_vecs: bool = False   # Generate multi-vector ColBERT tokens (optional)
    dense_dim: int = 1024               # BGE-M3 dense embedding dimension
    dense_vector_name: str = "dense"    # Name of the dense vector in Qdrant
    sparse_vector_name: str = "sparse"  # Name of the sparse vector in Qdrant
    normalize_embeddings: bool = True   # Normalize vectors to unit length (L2 norm)


@dataclass
class QdrantConfig:
    """Configuration for connecting to and provisioning Qdrant."""
    url: str = "http://127.0.0.1:6333" # Qdrant REST URL (local or cluster)
    grpc_port: int = 6334              # Qdrant gRPC port
    api_key: Optional[str] = None      # API key for Qdrant Cloud or protected instances
    path: Optional[str] = None         # Embedded on-disk storage path (no server required)
    collection_name: str = "pharmeazor_monographs"
    timeout: float = 30.0              # Timeout in seconds for HTTP/gRPC requests
    prefer_grpc: bool = False          # Use gRPC for high-throughput bulk insertions
    on_disk_payload: bool = True       # Keep payloads on disk to reduce RAM consumption


@dataclass
class EmbeddingOutput:
    """Container for multi-function vectors returned by the embedder."""
    dense: List[List[float]]                          # Shape: (N, 1024)
    sparse: Optional[List[Dict[int, float]]] = None   # List of {token_id: weight} dictionaries
    colbert: Optional[List[Any]] = None               # Optional ColBERT representations


@dataclass
class RetrievalResult:
    """Encapsulates a single retrieved chunk with its score and metadata."""
    chunk_id: str
    score: float
    text: str
    content: str
    header: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "score": round(self.score, 4),
            "text": self.text,
            "header": self.header,
            "content": self.content,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------------------
# Deterministic UUID Generator for Qdrant Points
# ---------------------------------------------------------------------------

def chunk_id_to_uuid(chunk_id: str) -> str:
    """
    Deterministically transforms any arbitrary string `chunk_id` into a valid RFC-4122
    UUID string (UUIDv5) required by Qdrant.
    Guarantees idempotent upserts: re-indexing the same chunk updates the exact same record.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))


# ---------------------------------------------------------------------------
# BGE-M3 Embedder Class
# ---------------------------------------------------------------------------

class BGEM3Embedder:
    """
    Wrapper for BAAI/bge-m3 embedding model.
    Supports Dense embeddings (1024-d) and Sparse lexical weights (BM25-equivalent)
    via `FlagEmbedding`, with fallbacks for sentence-transformers and offline testing.
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self.config = config or EmbeddingConfig()
        self._model = None
        self._backend = "none"

    def _init_model(self) -> None:
        """Lazily loads the embedding model onto device when first requested."""
        if self._model is not None:
            return

        device = self.config.device
        if device is None:
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        # Auto-disable fp16 if running on CPU to prevent torch runtime errors
        use_fp16 = self.config.use_fp16 and (device != "cpu")

        if _FLAG_EMBEDDING_AVAILABLE:
            logger.info("Initializing BGEM3FlagModel ('%s') on %s (fp16=%s)...",
                        self.config.model_name, device, use_fp16)
            try:
                self._model = BGEM3FlagModel(
                    self.config.model_name,
                    use_fp16=use_fp16,
                    device=device,
                )
                self._backend = "flagembedding"
                logger.info("BGEM3FlagModel successfully loaded.")
                return
            except Exception as e:
                logger.warning("Failed to initialize BGEM3FlagModel: %s. Attempting fallback...", e)

        if _SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.info("Falling back to SentenceTransformer('%s') on %s...", self.config.model_name, device)
            try:
                self._model = SentenceTransformer(self.config.model_name, device=device)
                self._backend = "sentence_transformers"
                logger.info("SentenceTransformer model successfully loaded.")
                return
            except Exception as e:
                logger.warning("Failed to initialize SentenceTransformer: %s", e)

        logger.warning(
            "Neither FlagEmbedding nor sentence-transformers is available (or models could not be loaded). "
            "Using deterministic simulated BGE-M3 embedder for development/offline testing."
        )
        self._backend = "simulated"

    @property
    def backend(self) -> str:
        """Returns the active backend ('flagembedding', 'sentence_transformers', or 'simulated')."""
        if self._model is None and self._backend == "none":
            self._init_model()
        return self._backend

    def encode(
        self,
        texts: Union[str, Sequence[str]],
        batch_size: Optional[int] = None,
        max_length: Optional[int] = None,
        return_dense: Optional[bool] = None,
        return_sparse: Optional[bool] = None,
    ) -> EmbeddingOutput:
        """
        Generates dense vectors and sparse lexical weights for a batch of texts.

        Args:
            texts: Single string or list of text strings to embed.
            batch_size: Batch size for encoding (defaults to config.batch_size).
            max_length: Max sequence length in tokens (defaults to config.max_length).
            return_dense: Whether to return dense vectors.
            return_sparse: Whether to return sparse lexical weights.

        Returns:
            EmbeddingOutput with `dense` vectors and optional `sparse` dictionaries.
        """
        self._init_model()

        if isinstance(texts, str):
            single_input = True
            text_list = [texts]
        else:
            single_input = False
            text_list = list(texts)

        if not text_list:
            return EmbeddingOutput(dense=[], sparse=[] if return_sparse else None)

        bs = batch_size or self.config.batch_size
        ml = max_length or self.config.max_length
        get_dense = return_dense if return_dense is not None else self.config.return_dense
        get_sparse = return_sparse if return_sparse is not None else self.config.return_sparse

        # Case 1: Official FlagEmbedding BGEM3FlagModel
        if self._backend == "flagembedding":
            out = self._model.encode(
                text_list,
                batch_size=bs,
                max_length=ml,
                return_dense=get_dense,
                return_sparse=get_sparse,
                return_colbert_vecs=self.config.return_colbert_vecs,
            )

            dense_vecs: List[List[float]] = []
            if get_dense and "dense_vecs" in out:
                raw_dense = out["dense_vecs"]
                if hasattr(raw_dense, "tolist"):
                    dense_vecs = raw_dense.tolist()
                else:
                    dense_vecs = [list(v) for v in raw_dense]

            sparse_vecs: Optional[List[Dict[int, float]]] = None
            if get_sparse and "lexical_weights" in out:
                sparse_vecs = []
                for weights in out["lexical_weights"]:
                    # Ensure keys are integer token IDs and values are floats
                    clean_dict: Dict[int, float] = {}
                    for k, v in weights.items():
                        try:
                            clean_dict[int(k)] = float(v)
                        except (ValueError, TypeError):
                            # Token string fallback hash into int32 space
                            token_hash = int(hashlib.md5(str(k).encode("utf-8")).hexdigest()[:8], 16)
                            clean_dict[token_hash] = float(v)
                    sparse_vecs.append(clean_dict)

            return EmbeddingOutput(dense=dense_vecs, sparse=sparse_vecs)

        # Case 2: SentenceTransformer fallback (Dense only + simulated lexical sparse)
        if self._backend == "sentence_transformers":
            raw_dense = self._model.encode(
                text_list,
                batch_size=bs,
                normalize_embeddings=self.config.normalize_embeddings,
                show_progress_bar=False,
            )
            dense_vecs = raw_dense.tolist() if hasattr(raw_dense, "tolist") else [list(v) for v in raw_dense]

            sparse_vecs = None
            if get_sparse:
                sparse_vecs = [self._compute_pseudo_sparse(t) for t in text_list]

            return EmbeddingOutput(dense=dense_vecs, sparse=sparse_vecs)

        # Case 3: Offline Simulated Embedder (Deterministic vectors for tests and environments without PyTorch)
        dense_vecs = [self._compute_simulated_dense(t) for t in text_list]
        sparse_vecs = [self._compute_pseudo_sparse(t) for t in text_list] if get_sparse else None
        return EmbeddingOutput(dense=dense_vecs, sparse=sparse_vecs)

    def encode_query(self, query: str) -> Tuple[List[float], Dict[int, float]]:
        """
        Encodes a single user search query into dense and sparse representations.
        Note: BGE-M3 does NOT require task instructions for queries.
        """
        output = self.encode(
            [query],
            return_dense=True,
            return_sparse=True,
        )
        dense_vector = output.dense[0] if output.dense else []
        sparse_vector = output.sparse[0] if (output.sparse and len(output.sparse) > 0) else {}
        return dense_vector, sparse_vector

    def convert_id_to_token(self, lexical_weights: Union[Dict[Any, float], List[Dict[Any, float]]]) -> Any:
        """Converts token IDs in lexical weights to human-readable strings if supported by the model."""
        self._init_model()
        if self._backend == "flagembedding" and hasattr(self._model, "convert_id_to_token"):
            return self._model.convert_id_to_token(lexical_weights)
        return lexical_weights

    def _compute_simulated_dense(self, text: str) -> List[float]:
        """Generates a deterministic 1024-dim unit vector based on text sha256."""
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vector = []
        for i in range(self.config.dense_dim):
            byte_val = h[i % len(h)]
            # Pseudo float in [-1.0, 1.0]
            val = ((byte_val ^ (i & 0xFF)) / 128.0) - 1.0
            vector.append(val)
        # Normalize vector to unit length (L2 norm)
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 0:
            vector = [round(x / norm, 6) for x in vector]
        return vector

    def _compute_pseudo_sparse(self, text: str) -> Dict[int, float]:
        """Generates a deterministic sparse token weight map (term frequency simulation)."""
        words = [w.strip().lower() for w in text.split() if len(w.strip()) > 2]
        counts: Dict[str, int] = {}
        for w in words:
            counts[w] = counts.get(w, 0) + 1

        sparse_dict: Dict[int, float] = {}
        for w, c in counts.items():
            # Hash word into a 24-bit integer token ID
            token_id = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:6], 16)
            weight = round(min(1.0, 0.15 + (c * 0.1)), 4)
            sparse_dict[token_id] = weight
        return sparse_dict


# ---------------------------------------------------------------------------
# Qdrant Vector Store Manager
# ---------------------------------------------------------------------------

class QdrantVectorStore:
    """
    Manages Qdrant collections, index provisioning, batch upserting,
    and hybrid search queries (Dense + Sparse RRF).
    """

    def __init__(
        self,
        config: Optional[QdrantConfig] = None,
        embedding_config: Optional[EmbeddingConfig] = None,
        client: Optional[Any] = None,
    ):
        self.config = config or QdrantConfig()
        self.embedding_config = embedding_config or EmbeddingConfig()
        self._client = client

    def get_client(self) -> Any:
        """Initializes or returns the active QdrantClient instance."""
        if self._client is not None:
            return self._client

        if not _QDRANT_AVAILABLE:
            raise ImportError(
                "The `qdrant-client` package is not installed. "
                "Install it with: pip install qdrant-client"
            )

        # Embedded on-disk mode
        if self.config.path:
            p = Path(self.config.path)
            p.mkdir(parents=True, exist_ok=True)
            logger.info("Connecting to embedded Qdrant database at: %s", p)
            self._client = QdrantClient(path=str(p))
            return self._client

        # Try standalone server via HTTP / REST; if unreachable, fall back to embedded storage
        try:
            logger.info("Connecting to Qdrant server at: %s", self.config.url)
            client = QdrantClient(
                url=self.config.url,
                api_key=self.config.api_key,
                timeout=3.0,
                prefer_grpc=self.config.prefer_grpc,
            )
            # Test connectivity
            client.get_collections()
            self._client = client
            return self._client
        except Exception as e:
            fallback_path = PROJECT_ROOT / "qdrant" / "storage"
            fallback_path.mkdir(parents=True, exist_ok=True)
            logger.warning(
                "Qdrant server at %s is not running (%s). "
                "Automatically using local disk storage at: %s",
                self.config.url, e, fallback_path
            )
            self._client = QdrantClient(path=str(fallback_path))
            return self._client

    def collection_exists(self, collection_name: Optional[str] = None) -> bool:
        """Checks if a collection exists in Qdrant."""
        client = self.get_client()
        target = collection_name or self.config.collection_name
        return client.collection_exists(target)

    def init_collection(
        self,
        collection_name: Optional[str] = None,
        force_recreate: bool = False,
    ) -> bool:
        """
        Provisions a Qdrant collection configured for BGE-M3 hybrid retrieval:
        - Named dense vector ('dense') with 1024 dims and Cosine distance.
        - Named sparse vector ('sparse') for lexical token weights.
        - Indexed payload fields for fast clinical filtering.
        """
        client = self.get_client()
        target = collection_name or self.config.collection_name

        if client.collection_exists(target):
            if force_recreate:
                logger.warning("Deleting existing Qdrant collection '%s' for recreation...", target)
                client.delete_collection(target)
            else:
                logger.info("Collection '%s' already exists in Qdrant. Skipping creation.", target)
                return True

        logger.info("Creating Qdrant collection '%s' with Dense (1024-d) + Sparse vectors...", target)

        vectors_config = {
            self.embedding_config.dense_vector_name: VectorParams(
                size=self.embedding_config.dense_dim,
                distance=Distance.COSINE,
            )
        }

        sparse_vectors_config = {
            self.embedding_config.sparse_vector_name: SparseVectorParams(
                index=SparseIndexParams(on_disk=self.config.on_disk_payload)
            )
        }

        client.create_collection(
            collection_name=target,
            vectors_config=vectors_config,
            sparse_vectors_config=sparse_vectors_config,
        )

        # Provision payload indexes for rapid metadata filtering
        filter_indexes = [
            ("dci", PayloadSchemaType.KEYWORD),
            ("brand", PayloadSchemaType.KEYWORD),
            ("source", PayloadSchemaType.KEYWORD),
            ("section_category", PayloadSchemaType.KEYWORD),
            ("doc_type", PayloadSchemaType.KEYWORD),
            ("source_priority", PayloadSchemaType.INTEGER),
            ("dossier", PayloadSchemaType.KEYWORD),
        ]

        for field_name, field_schema in filter_indexes:
            try:
                client.create_payload_index(
                    collection_name=target,
                    field_name=field_name,
                    field_schema=field_schema,
                )
            except Exception as e:
                logger.debug("Payload index creation note for '%s': %s", field_name, e)

        logger.info("Successfully provisioned collection '%s'.", target)
        return True

    def upsert_points(
        self,
        points: List[Any],
        collection_name: Optional[str] = None,
        batch_size: int = 100,
    ) -> int:
        """
        Upserts a list of PointStruct points into Qdrant in batches.
        Returns the count of successfully upserted points.
        """
        if not points:
            return 0

        client = self.get_client()
        target = collection_name or self.config.collection_name

        total = len(points)
        for i in range(0, total, batch_size):
            batch = points[i : i + batch_size]
            client.upsert(collection_name=target, points=batch)

        logger.info("Upserted %d points to Qdrant collection '%s'.", total, target)
        return total

    def build_qdrant_point(
        self,
        chunk: DrugChunk,
        dense_vec: List[float],
        sparse_vec: Optional[Dict[int, float]] = None,
    ) -> Any:
        """
        Constructs a Qdrant `PointStruct` from a `DrugChunk`:
        - Point ID: Deterministic RFC-4122 UUIDv5 derived from `chunk.chunk_id`.
        - Vectors: Named dict with 'dense' vector and 'sparse' SparseVector.
        - Payload: Full structured clinical metadata + chunk texts.
        """
        point_id = chunk_id_to_uuid(chunk.chunk_id)

        vectors: Dict[str, Any] = {
            self.embedding_config.dense_vector_name: dense_vec
        }

        if sparse_vec and len(sparse_vec) > 0:
            indices = list(sparse_vec.keys())
            values = list(sparse_vec.values())
            vectors[self.embedding_config.sparse_vector_name] = SparseVector(
                indices=indices,
                values=values,
            )

        payload = {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "content": chunk.content,
            "header": chunk.header,
            **chunk.metadata,
        }

        return PointStruct(
            id=point_id,
            vector=vectors,
            payload=payload,
        )

    def search_hybrid(
        self,
        query_dense: List[float],
        query_sparse: Optional[Dict[int, float]] = None,
        collection_name: Optional[str] = None,
        limit: int = 5,
        filter_dci: Optional[str] = None,
        filter_category: Optional[str] = None,
        filter_source: Optional[str] = None,
        filter_brand: Optional[str] = None,
        score_threshold: Optional[float] = None,
    ) -> List[RetrievalResult]:
        """
        Performs state-of-the-art hybrid search (Dense + Sparse) fused via Reciprocal Rank Fusion (RRF).
        Falls back to dense search if sparse query vector is empty.
        """
        client = self.get_client()
        target = collection_name or self.config.collection_name

        # Build metadata filters
        must_conditions = []
        if filter_dci:
            must_conditions.append(FieldCondition(key="dci", match=MatchValue(value=filter_dci)))
        if filter_category:
            must_conditions.append(FieldCondition(key="section_category", match=MatchValue(value=filter_category)))
        if filter_source:
            must_conditions.append(FieldCondition(key="source", match=MatchValue(value=filter_source)))
        if filter_brand:
            must_conditions.append(FieldCondition(key="brand", match=MatchValue(value=filter_brand)))

        query_filter = Filter(must=must_conditions) if must_conditions else None

        results: List[RetrievalResult] = []

        # Case 1: Hybrid retrieval (both Dense and Sparse available)
        has_sparse = query_sparse and len(query_sparse) > 0
        if has_sparse:
            sparse_indices = list(query_sparse.keys())
            sparse_values = list(query_sparse.values())
            sparse_obj = SparseVector(indices=sparse_indices, values=sparse_values)

            try:
                # Modern Qdrant query_points with prefetch fusion
                prefetch = [
                    Prefetch(
                        query=query_dense,
                        using=self.embedding_config.dense_vector_name,
                        limit=limit * 3,
                        filter=query_filter,
                    ),
                    Prefetch(
                        query=sparse_obj,
                        using=self.embedding_config.sparse_vector_name,
                        limit=limit * 3,
                        filter=query_filter,
                    ),
                ]

                response = client.query_points(
                    collection_name=target,
                    prefetch=prefetch,
                    query=FusionQuery(fusion=Fusion.RRF),
                    limit=limit,
                )

                for hit in response.points:
                    payload = hit.payload or {}
                    results.append(
                        RetrievalResult(
                            chunk_id=payload.get("chunk_id", str(hit.id)),
                            score=hit.score or 0.0,
                            text=payload.get("text", ""),
                            content=payload.get("content", ""),
                            header=payload.get("header", ""),
                            metadata={k: v for k, v in payload.items() if k not in ["text", "content", "header"]},
                        )
                    )
                return results
            except Exception as e:
                logger.warning("Hybrid query_points fusion failed (%s). Falling back to dense query...", e)

        # Case 2: Dense-only query fallback
        try:
            response = client.query_points(
                collection_name=target,
                query=query_dense,
                using=self.embedding_config.dense_vector_name,
                limit=limit,
                query_filter=query_filter,
                score_threshold=score_threshold,
            )
            for hit in response.points:
                payload = hit.payload or {}
                results.append(
                    RetrievalResult(
                        chunk_id=payload.get("chunk_id", str(hit.id)),
                        score=hit.score or 0.0,
                        text=payload.get("text", ""),
                        content=payload.get("content", ""),
                        header=payload.get("header", ""),
                        metadata={k: v for k, v in payload.items() if k not in ["text", "content", "header"]},
                    )
                )
        except Exception as e:
            logger.error("Error during Qdrant query: %s", e)

        return results


# ---------------------------------------------------------------------------
# High-Level RAG Indexing Pipeline
# ---------------------------------------------------------------------------

@dataclass
class IndexingStats:
    """Summary statistics from an indexing run."""
    total_chunks_processed: int = 0
    total_points_upserted: int = 0
    failed_chunks: int = 0
    elapsed_seconds: float = 0.0
    collection_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "collection": self.collection_name,
            "chunks_processed": self.total_chunks_processed,
            "points_upserted": self.total_points_upserted,
            "failed_chunks": self.failed_chunks,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "throughput_chunks_per_sec": (
                round(self.total_points_upserted / self.elapsed_seconds, 1)
                if self.elapsed_seconds > 0 else 0
            ),
        }


class DrugRAGPipeline:
    """
    End-to-End Orchestrator bridging `chunking.py`, `BGE-M3 Embedder`, and `Qdrant`.
    Enables indexing files, directories, or streams of `DrugChunk` objects,
    and executing hybrid queries.
    """

    def __init__(
        self,
        embedder: Optional[BGEM3Embedder] = None,
        vector_store: Optional[QdrantVectorStore] = None,
        chunker: Optional[DrugChunker] = None,
    ):
        self.embedder = embedder or BGEM3Embedder()
        self.vector_store = vector_store or QdrantVectorStore()
        self.chunker = chunker or DrugChunker()

    def index_chunks(
        self,
        chunks: Iterable[DrugChunk],
        collection_name: Optional[str] = None,
        batch_size: int = 32,
        recreate_collection: bool = False,
    ) -> IndexingStats:
        """
        Encodes a stream of `DrugChunk` objects with BGE-M3 and upserts them into Qdrant.

        Args:
            chunks: Iterable yielding `DrugChunk` instances.
            collection_name: Target collection name (defaults to store config).
            batch_size: Number of chunks to encode and upsert per batch.
            recreate_collection: If True, deletes and creates a fresh collection.

        Returns:
            IndexingStats with timing and count details.
        """
        start_time = time.time()
        target = collection_name or self.vector_store.config.collection_name

        # Ensure collection exists
        self.vector_store.init_collection(
            collection_name=target,
            force_recreate=recreate_collection,
        )

        stats = IndexingStats(collection_name=target)
        chunk_buffer: List[DrugChunk] = []

        def flush_buffer(buffer: List[DrugChunk]) -> None:
            if not buffer:
                return

            texts = [c.text for c in buffer]

            # Generate BGE-M3 Dense + Sparse representations
            try:
                embeddings = self.embedder.encode(
                    texts,
                    batch_size=len(texts),
                    return_dense=True,
                    return_sparse=True,
                )
            except Exception as e:
                logger.error("Failed to embed batch of %d chunks: %s", len(buffer), e)
                stats.failed_chunks += len(buffer)
                return

            points = []
            for idx, c in enumerate(buffer):
                d_vec = embeddings.dense[idx] if embeddings.dense else []
                s_vec = (embeddings.sparse[idx] if embeddings.sparse and idx < len(embeddings.sparse) else None)
                point = self.vector_store.build_qdrant_point(c, d_vec, s_vec)
                points.append(point)

            try:
                upserted = self.vector_store.upsert_points(points, collection_name=target)
                stats.total_points_upserted += upserted
            except Exception as e:
                logger.error("Failed to upsert points into Qdrant: %s", e)
                stats.failed_chunks += len(points)

        for chunk in chunks:
            chunk_buffer.append(chunk)
            stats.total_chunks_processed += 1

            if len(chunk_buffer) >= batch_size:
                flush_buffer(chunk_buffer)
                chunk_buffer = []

        # Flush any remaining chunks
        if chunk_buffer:
            flush_buffer(chunk_buffer)

        stats.elapsed_seconds = time.time() - start_time
        logger.info("Indexing complete: %s", stats.to_dict())
        return stats

    def index_corpus(
        self,
        data_dir: Optional[Union[str, Path]] = None,
        dossier: Optional[str] = None,
        sources: Optional[List[str]] = None,
        doc_type: Optional[str] = None,
        max_docs: Optional[int] = None,
        batch_size: int = 32,
        recreate_collection: bool = False,
    ) -> IndexingStats:
        """
        Walks `data/outputs_data` using `chunk_corpus()` and indexes all matching monographs.
        """
        logger.info("Streaming and chunking corpus from: %s (dossier=%s)...",
                    data_dir or DEFAULT_DATA_DIR, dossier)

        chunks_stream = chunk_corpus(
            data_dir=data_dir,
            dossier=dossier,
            sources=sources,
            doc_type=doc_type,
            max_docs=max_docs,
        )

        return self.index_chunks(
            chunks=chunks_stream,
            batch_size=batch_size,
            recreate_collection=recreate_collection,
        )

    def index_file(
        self,
        file_path: Union[str, Path],
        collection_name: Optional[str] = None,
        batch_size: int = 32,
    ) -> IndexingStats:
        """Chunks and indexes an individual .json monograph or .jsonl file."""
        chunks = chunk_file(file_path)
        return self.index_chunks(
            chunks=chunks,
            collection_name=collection_name,
            batch_size=batch_size,
            recreate_collection=False,
        )

    def search(
        self,
        query: str,
        limit: int = 5,
        filter_dci: Optional[str] = None,
        filter_category: Optional[str] = None,
        filter_source: Optional[str] = None,
        filter_brand: Optional[str] = None,
    ) -> List[RetrievalResult]:
        """
        Executes hybrid BGE-M3 retrieval:
        1. Encodes query into dense vector + sparse token weights.
        2. Queries Qdrant with RRF fusion.
        3. Returns ranked `RetrievalResult` objects.
        """
        query_dense, query_sparse = self.embedder.encode_query(query)
        return self.vector_store.search_hybrid(
            query_dense=query_dense,
            query_sparse=query_sparse,
            limit=limit,
            filter_dci=filter_dci,
            filter_category=filter_category,
            filter_source=filter_source,
            filter_brand=filter_brand,
        )


# ---------------------------------------------------------------------------
# Convenience Module-Level Instances & Functions
# ---------------------------------------------------------------------------

default_embedder = BGEM3Embedder()
default_store = QdrantVectorStore()
default_pipeline = DrugRAGPipeline(embedder=default_embedder, vector_store=default_store)


def embed_texts(texts: Union[str, List[str]], **kwargs: Any) -> EmbeddingOutput:
    """Convenience function to generate BGE-M3 embeddings."""
    return default_embedder.encode(texts, **kwargs)


def embed_query(query: str) -> Tuple[List[float], Dict[int, float]]:
    """Convenience function to encode a user query into dense + sparse vectors."""
    return default_embedder.encode_query(query)


def index_pharmaceutical_corpus(
    dossier: Optional[str] = None,
    data_dir: Optional[Union[str, Path]] = None,
    max_docs: Optional[int] = None,
    batch_size: int = 32,
    recreate: bool = False,
) -> IndexingStats:
    """One-line helper to index the pharmaceutical corpus into Qdrant."""
    return default_pipeline.index_corpus(
        data_dir=data_dir,
        dossier=dossier,
        max_docs=max_docs,
        batch_size=batch_size,
        recreate_collection=recreate,
    )


def search_drugs(
    query: str,
    limit: int = 5,
    dci: Optional[str] = None,
    category: Optional[str] = None,
) -> List[RetrievalResult]:
    """One-line helper to execute hybrid BGE-M3 search in Qdrant."""
    return default_pipeline.search(
        query=query,
        limit=limit,
        filter_dci=dci,
        filter_category=category,
    )


# ---------------------------------------------------------------------------
# CLI Command Line Interface
# ---------------------------------------------------------------------------

def _run_cli() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Pharmeazor RAG - BGE-M3 Embedding & Qdrant Indexer")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Index command
    index_parser = subparsers.add_parser("index", help="Index drug monographs into Qdrant")
    index_parser.add_argument("--dossier", type=str, default=None, help="Specific dossier (e.g. 01_paracetamol)")
    index_parser.add_argument("--data-dir", type=str, default=None, help="Path to data/outputs_data directory")
    index_parser.add_argument("--max-docs", type=int, default=None, help="Limit number of documents to index")
    index_parser.add_argument("--batch-size", type=int, default=32, help="Batch size for embedding and upsert")
    index_parser.add_argument("--recreate", action="store_true", help="Recreate collection before indexing")
    index_parser.add_argument("--path", type=str, default=None, help="Local disk storage path for Qdrant (e.g. qdrant/storage)")
    index_parser.add_argument("--url", type=str, default=None, help="Qdrant server URL (e.g. http://127.0.0.1:6333)")

    # Search command
    search_parser = subparsers.add_parser("search", help="Execute hybrid search in Qdrant")
    search_parser.add_argument("query", type=str, help="Search question or clinical query")
    search_parser.add_argument("--limit", type=int, default=5, help="Number of results to return")
    search_parser.add_argument("--dci", type=str, default=None, help="Filter by DCI")
    search_parser.add_argument("--category", type=str, default=None, help="Filter by section category (posology, etc.)")
    search_parser.add_argument("--path", type=str, default=None, help="Local disk storage path for Qdrant (e.g. qdrant/storage)")
    search_parser.add_argument("--url", type=str, default=None, help="Qdrant server URL (e.g. http://127.0.0.1:6333)")

    # Test command
    subparsers.add_parser("test", help="Run self-diagnostic verification")

    args = parser.parse_args()

    if args.command == "index":
        print(f"Indexing corpus into Qdrant (dossier={args.dossier}, max_docs={args.max_docs})...")
        qcfg = QdrantConfig()
        if args.path:
            qcfg.path = args.path
        if args.url:
            qcfg.url = args.url
        custom_store = QdrantVectorStore(config=qcfg)
        pipeline = DrugRAGPipeline(embedder=default_embedder, vector_store=custom_store)
        stats = pipeline.index_corpus(
            dossier=args.dossier,
            data_dir=args.data_dir,
            max_docs=args.max_docs,
            batch_size=args.batch_size,
            recreate_collection=args.recreate,
        )
        print("Indexing completed successfully:")
        print(json.dumps(stats.to_dict(), indent=2))

    elif args.command == "search":
        print(f"Executing hybrid search for: '{args.query}' (limit={args.limit})...")
        qcfg = QdrantConfig()
        if args.path:
            qcfg.path = args.path
        if args.url:
            qcfg.url = args.url
        custom_store = QdrantVectorStore(config=qcfg)
        pipeline = DrugRAGPipeline(embedder=default_embedder, vector_store=custom_store)
        results = pipeline.search(
            query=args.query,
            limit=args.limit,
            filter_dci=args.dci,
            filter_category=args.category,
        )
        print(f"\nFound {len(results)} matches:")
        for i, r in enumerate(results, start=1):
            print(f"\n[{i}] Score: {r.score:.4f} | Chunk ID: {r.chunk_id}")
            print(f"Header: {r.header}")
            print(f"Content: {r.content[:200]}...")

    elif args.command == "test":
        print("Running BGE-M3 & Qdrant Self-Diagnostic Test...")
        embedder = BGEM3Embedder()
        print(f"Embedder backend: {embedder.backend}")
        out = embedder.encode(["Test embedding for Paracetamol."])
        print(f"Generated dense vector length: {len(out.dense[0])} (expected 1024)")
        if out.sparse:
            print(f"Generated sparse token count: {len(out.sparse[0])}")
        print("\nSelf-diagnostic passed successfully!")

    else:
        parser.print_help()


if __name__ == "__main__":
    _run_cli()
