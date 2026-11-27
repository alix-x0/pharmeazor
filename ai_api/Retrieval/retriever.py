"""
Pharmeazor RAG System - Retrieval & Pipeline Engine
===================================================
Coordinates chunking, embedding, indexing, and hybrid retrieval (Dense + Sparse RRF).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

logger = logging.getLogger(__name__)

# Ensure project root in path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Retrieval.chunking import (
    DEFAULT_DATA_DIR,
    DrugChunk,
    DrugChunker,
    chunk_corpus,
    chunk_file,
)
from ai_api.Retrieval.embedding import (
    BGEM3Embedder,
    default_embedder,
)
from ai_api.Retrieval.vector_store import (
    QdrantConfig,
    QdrantVectorStore,
    default_store,
)

try:
    from qdrant_client.models import (
        FieldCondition,
        Filter,
        Fusion,
        FusionQuery,
        MatchValue,
        Prefetch,
        SparseVector,
    )
except ImportError:
    FieldCondition = None  # type: ignore
    Filter = None  # type: ignore
    Fusion = None  # type: ignore
    FusionQuery = None  # type: ignore
    MatchValue = None  # type: ignore
    Prefetch = None  # type: ignore
    SparseVector = None  # type: ignore


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
        self.embedder = embedder or default_embedder
        self.vector_store = vector_store or default_store
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
        """
        start_time = time.time()
        target = collection_name or self.vector_store.config.collection_name

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
        """Walks `data/outputs_data` using `chunk_corpus()` and indexes all matching monographs."""
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
        score_threshold: Optional[float] = None,
    ) -> List[RetrievalResult]:
        """
        Executes hybrid BGE-M3 retrieval:
        1. Encodes query into dense vector + sparse token weights.
        2. Queries Qdrant with RRF fusion.
        3. Returns ranked `RetrievalResult` objects.
        """
        client = self.vector_store.get_client()
        target = self.vector_store.config.collection_name

        query_dense, query_sparse = self.embedder.encode_query(query)

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

        # Hybrid query with prefetch & RRF
        has_sparse = query_sparse and len(query_sparse) > 0
        if has_sparse:
            sparse_indices = list(query_sparse.keys())
            sparse_values = list(query_sparse.values())
            sparse_obj = SparseVector(indices=sparse_indices, values=sparse_values)

            try:
                prefetch = [
                    Prefetch(
                        query=query_dense,
                        using=self.vector_store.embedding_config.dense_vector_name,
                        limit=limit * 3,
                        filter=query_filter,
                    ),
                    Prefetch(
                        query=sparse_obj,
                        using=self.vector_store.embedding_config.sparse_vector_name,
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
                    p = hit.payload or {}
                    results.append(
                        RetrievalResult(
                            chunk_id=p.get("chunk_id", str(hit.id)),
                            score=hit.score or 0.0,
                            text=p.get("text", ""),
                            content=p.get("content", ""),
                            header=p.get("header", ""),
                            metadata={k: v for k, v in p.items() if k not in ["text", "content", "header"]},
                        )
                    )
                return results
            except Exception as e:
                logger.warning("Hybrid fusion failed (%s). Falling back to dense query...", e)

        # Dense-only fallback
        try:
            response = client.query_points(
                collection_name=target,
                query=query_dense,
                using=self.vector_store.embedding_config.dense_vector_name,
                limit=limit,
                query_filter=query_filter,
                score_threshold=score_threshold,
            )
            for hit in response.points:
                p = hit.payload or {}
                results.append(
                    RetrievalResult(
                        chunk_id=p.get("chunk_id", str(hit.id)),
                        score=hit.score or 0.0,
                        text=p.get("text", ""),
                        content=p.get("content", ""),
                        header=p.get("header", ""),
                        metadata={k: v for k, v in p.items() if k not in ["text", "content", "header"]},
                    )
                )
        except Exception as e:
            logger.error("Error during Qdrant query: %s", e)

        return results


default_pipeline = DrugRAGPipeline()


def index_pharmaceutical_corpus(
    dossier: Optional[str] = None,
    data_dir: Optional[Union[str, Path]] = None,
    max_docs: Optional[int] = None,
    batch_size: int = 32,
    recreate: bool = False,
) -> IndexingStats:
    """Helper to index the pharmaceutical corpus into Qdrant."""
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
    """Helper to execute hybrid BGE-M3 search in Qdrant."""
    return default_pipeline.search(
        query=query,
        limit=limit,
        filter_dci=dci,
        filter_category=category,
    )


def _run_cli() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Pharmeazor Retrieval - BGE-M3 Embedding & Qdrant Indexer")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    index_parser = subparsers.add_parser("index", help="Index drug monographs into Qdrant")
    index_parser.add_argument("--dossier", type=str, default=None, help="Specific dossier (e.g. 01_paracetamol)")
    index_parser.add_argument("--data-dir", type=str, default=None, help="Path to data/outputs_data directory")
    index_parser.add_argument("--max-docs", type=int, default=None, help="Limit number of documents to index")
    index_parser.add_argument("--batch-size", type=int, default=32, help="Batch size for embedding and upsert")
    index_parser.add_argument("--recreate", action="store_true", help="Recreate collection before indexing")
    index_parser.add_argument("--path", type=str, default=None, help="Local disk storage path for Qdrant (e.g. qdrant/storage)")
    index_parser.add_argument("--url", type=str, default=None, help="Qdrant server URL (e.g. http://127.0.0.1:6333)")

    search_parser = subparsers.add_parser("search", help="Execute hybrid search in Qdrant")
    search_parser.add_argument("query", type=str, help="Search question or clinical query")
    search_parser.add_argument("--limit", type=int, default=5, help="Number of results to return")
    search_parser.add_argument("--dci", type=str, default=None, help="Filter by DCI")
    search_parser.add_argument("--category", type=str, default=None, help="Filter by section category (posology, etc.)")
    search_parser.add_argument("--path", type=str, default=None, help="Local disk storage path for Qdrant (e.g. qdrant/storage)")
    search_parser.add_argument("--url", type=str, default=None, help="Qdrant server URL (e.g. http://127.0.0.1:6333)")

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
