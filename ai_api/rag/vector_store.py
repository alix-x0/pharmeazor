"""
Pharmeazor RAG System - Qdrant Vector Store Manager
===================================================
Manages Qdrant dual-vector collections (Dense + Sparse), index provisioning,
point conversions, and batch upserts.
"""

from __future__ import annotations

import logging
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Ensure project root in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.rag.chunking import DrugChunk
from ai_api.rag.embedding import EmbeddingConfig

# Optional Qdrant dependency with safe dataclass stand-ins
_QDRANT_AVAILABLE = False

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


def chunk_id_to_uuid(chunk_id: str) -> str:
    """
    Deterministically transforms any arbitrary string `chunk_id` into a valid RFC-4122
    UUID string (UUIDv5) required by Qdrant.
    Guarantees idempotent upserts: re-indexing the same chunk updates the exact same record.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, chunk_id))


class QdrantVectorStore:
    """
    Manages Qdrant collections, index provisioning, and batch upserting.
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

        # Embedded on-disk mode if explicitly requested
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
                logger.debug("Payload index note for '%s': %s", field_name, e)

        logger.info("Successfully provisioned collection '%s'.", target)
        return True

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

    def upsert_points(
        self,
        points: List[Any],
        collection_name: Optional[str] = None,
        batch_size: int = 100,
    ) -> int:
        """
        Upserts a list of PointStruct points into Qdrant in batches.
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


default_store = QdrantVectorStore()
