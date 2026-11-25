"""
Test Suite for Pharmeazor BGE-M3 Embedding & Qdrant Integration Engine
======================================================================
Tests multi-functionality embeddings (Dense 1024-d, Sparse lexical weights),
deterministic UUID point generation, Qdrant payload structuring, and seamless
interoperability with `chunking.py`.

Run:
    python -m ai_api.Retrieval.embedding_test
"""

from __future__ import annotations

import json
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Retrieval.chunking import (
    DEFAULT_DATA_DIR,
    ChunkingConfig,
    DrugChunk,
    DrugChunker,
    chunk_corpus,
    chunk_document,
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
    embed_query,
    embed_texts,
)


class TestEmbeddingUnit(unittest.TestCase):
    """Unit tests for BGE-M3 Embedder, configurations, and UUID formatting."""

    def test_embedding_config_defaults(self):
        """Test default parameters of EmbeddingConfig."""
        cfg = EmbeddingConfig()
        self.assertEqual(cfg.model_name, "BAAI/bge-m3")
        self.assertEqual(cfg.dense_dim, 1024)
        self.assertEqual(cfg.max_length, 8192)
        self.assertTrue(cfg.return_dense)
        self.assertTrue(cfg.return_sparse)
        self.assertEqual(cfg.dense_vector_name, "dense")
        self.assertEqual(cfg.sparse_vector_name, "sparse")

    def test_qdrant_config_defaults(self):
        """Test default parameters of QdrantConfig."""
        qcfg = QdrantConfig()
        self.assertEqual(qcfg.url, "http://127.0.0.1:6333")
        self.assertEqual(qcfg.collection_name, "pharmeazor_monographs")
        self.assertEqual(qcfg.grpc_port, 6334)
        self.assertTrue(qcfg.on_disk_payload)

    def test_chunk_id_to_uuid_deterministic(self):
        """Test that chunk_id_to_uuid produces identical, valid RFC-4122 UUIDs."""
        chunk_id = "chk_anpp_posology_1_abc123"
        id1 = chunk_id_to_uuid(chunk_id)
        id2 = chunk_id_to_uuid(chunk_id)

        # Must be identical (idempotency)
        self.assertEqual(id1, id2)

        # Must parse as a valid UUID
        parsed = uuid.UUID(id1)
        self.assertEqual(str(parsed), id1)
        self.assertEqual(parsed.version, 5)

        # Different chunk IDs must produce different UUIDs
        id3 = chunk_id_to_uuid("chk_anpp_posology_2_xyz789")
        self.assertNotEqual(id1, id3)

    def test_embedder_encode_dense_and_sparse(self):
        """Test that the embedder generates 1024-dim dense vectors and token weights."""
        embedder = BGEM3Embedder()
        texts = [
            "Doliprane 1000 mg comprimé. Posologie: 1 comprimé 3 fois par jour.",
            "Ibuprofène 400 mg. Contre-indications: ulcère gastroduodénal actif.",
        ]

        output = embedder.encode(texts, return_dense=True, return_sparse=True)
        self.assertIsInstance(output, EmbeddingOutput)
        self.assertEqual(len(output.dense), 2)

        # Verify dense dimensions
        for dense_vec in output.dense:
            self.assertEqual(len(dense_vec), 1024)
            # Check unit length (L2 norm)
            norm = sum(x * x for x in dense_vec) ** 0.5
            self.assertAlmostEqual(norm, 1.0, places=2)

        # Verify sparse lexical representations
        self.assertIsNotNone(output.sparse)
        self.assertEqual(len(output.sparse), 2)
        for sparse_map in output.sparse:
            self.assertIsInstance(sparse_map, dict)
            self.assertGreater(len(sparse_map), 0)
            for token_id, weight in sparse_map.items():
                self.assertIsInstance(token_id, int)
                self.assertIsInstance(weight, float)
                self.assertGreater(weight, 0.0)

    def test_embed_query(self):
        """Test encoding a single user clinical question."""
        embedder = BGEM3Embedder()
        question = "Quelle est la dose maximale journalière de paracétamol chez l'adulte ?"
        dense_vec, sparse_vec = embedder.encode_query(question)

        self.assertEqual(len(dense_vec), 1024)
        self.assertIsInstance(sparse_vec, dict)
        self.assertGreater(len(sparse_vec), 0)


class TestChunkingAndQdrantIntegration(unittest.TestCase):
    """Tests the bridge between `chunking.py` output and Qdrant PointStruct objects."""

    def setUp(self):
        self.chunker = DrugChunker()
        self.embedder = BGEM3Embedder()
        self.store = QdrantVectorStore()

        # Realistic mock pharmaceutical monograph document
        self.sample_doc = {
            "source": "anpp",
            "source_priority": 1,
            "drug_id": 101,
            "brand": "DOLIPRANE",
            "dci": "PARACÉTAMOL",
            "lab": "PROPHARMAL SPA",
            "dosage": "1000 mg",
            "form": "comprimé",
            "doc_type": "rcp",
            "language": "fr",
            "sections": [
                {
                    "number": "4.1",
                    "title": "Indications thérapeutiques",
                    "key": "indications",
                    "text": "Traitement symptomatique des douleurs d'intensité légère à modérée et/ou des états fébriles.",
                },
                {
                    "number": "4.2",
                    "title": "Posologie et mode d'administration",
                    "key": "posologie",
                    "text": "Cette présentation est réservée à l'adulte et à l'enfant à partir de 50 kg. La posologie usuelle est de 1 comprimé à 1000 mg par prise, à renouveler en cas de besoin au bout de 4 heures minimum. Ne pas dépasser 3 g par jour sans avis médical.",
                },
                {
                    "number": "4.3",
                    "title": "Contre-indications",
                    "key": "contre_indications",
                    "text": "Hypersensibilité au principe actif ou à l'un des excipients. Insuffisance hépatocellulaire sévère.",
                },
            ],
        }

    def test_chunking_to_qdrant_points(self):
        """Test end-to-end chunking and conversion to Qdrant PointStruct points."""
        chunks = self.chunker.chunk_document(self.sample_doc, dossier="01_paracetamol")
        self.assertEqual(len(chunks), 3)

        # Encode chunks
        texts = [c.text for c in chunks]
        embeddings = self.embedder.encode(texts)

        # Convert each chunk to a Qdrant point
        points = []
        for i, c in enumerate(chunks):
            p = self.store.build_qdrant_point(
                chunk=c,
                dense_vec=embeddings.dense[i],
                sparse_vec=embeddings.sparse[i] if embeddings.sparse else None,
            )
            points.append(p)

        self.assertEqual(len(points), 3)

        # Validate first point structure
        p0 = points[0]
        # Point ID is a valid UUIDv5
        uuid_obj = uuid.UUID(p0.id)
        self.assertEqual(str(uuid_obj), p0.id)

        # Vector dict contains named 'dense' and 'sparse' vectors
        self.assertIn("dense", p0.vector)
        self.assertEqual(len(p0.vector["dense"]), 1024)

        if "sparse" in p0.vector:
            sparse_obj = p0.vector["sparse"]
            self.assertTrue(hasattr(sparse_obj, "indices"))
            self.assertTrue(hasattr(sparse_obj, "values"))
            self.assertEqual(len(sparse_obj.indices), len(sparse_obj.values))

        # Payload contains chunk content and clinical metadata
        payload = p0.payload
        self.assertEqual(payload["brand"], "DOLIPRANE")
        self.assertEqual(payload["dci"], "PARACÉTAMOL")
        self.assertEqual(payload["source"], "anpp")
        self.assertEqual(payload["source_priority"], 1)
        self.assertEqual(payload["section_category"], "indications")
        self.assertIn("text", payload)
        self.assertIn("content", payload)
        self.assertIn("header", payload)

    def test_pipeline_with_mock_client(self):
        """Test DrugRAGPipeline execution using a mock Qdrant client."""
        mock_client = MagicMock()
        mock_client.collection_exists.return_value = False
        mock_client.upsert.return_value = True

        custom_store = QdrantVectorStore(client=mock_client)
        pipeline = DrugRAGPipeline(embedder=self.embedder, vector_store=custom_store, chunker=self.chunker)

        chunks = self.chunker.chunk_document(self.sample_doc)
        stats = pipeline.index_chunks(chunks, batch_size=2)

        self.assertEqual(stats.total_chunks_processed, 3)
        self.assertEqual(stats.total_points_upserted, 3)
        self.assertEqual(stats.failed_chunks, 0)
        self.assertTrue(mock_client.create_collection.called)
        self.assertTrue(mock_client.upsert.called)


class TestRealDatasetChunkingToEmbeddings(unittest.TestCase):
    """Tests chunking and embedding generation using actual data in data/outputs_data."""

    def test_stream_chunks_and_embed_batch(self):
        """Verify streaming chunks from outputs_data and generating BGE-M3 representations."""
        if not DEFAULT_DATA_DIR.exists():
            self.skipTest(f"Data directory not found at {DEFAULT_DATA_DIR}")

        stream = chunk_corpus(DEFAULT_DATA_DIR, dossier="01_paracetamol", max_docs=1)
        first_chunks = []
        for c in stream:
            first_chunks.append(c)
            if len(first_chunks) >= 5:
                break

        self.assertGreater(len(first_chunks), 0)

        embedder = BGEM3Embedder()
        output = embedder.encode([c.text for c in first_chunks])

        self.assertEqual(len(output.dense), len(first_chunks))
        self.assertEqual(len(output.dense[0]), 1024)
        if output.sparse:
            self.assertEqual(len(output.sparse), len(first_chunks))


def display_sample_embedding() -> None:
    """
    Encodes a realistic clinical chunk using BGE-M3 and prints a detailed
    breakdown of the dense vector, sparse lexical weights, and Qdrant point.
    """
    print("\n" + "=" * 70)
    print("SAMPLE BGE-M3 EMBEDDING & QDRANT POINT VISUALIZATION")
    print("=" * 70)

    # 1. Realistic clinical chunk
    header = "[MÉDICAMENT: DOLIPRANE | DCI: PARACÉTAMOL | FORME/DOSAGE: 1000 mg comprimé | LABO: PROPHARMAL SPA | SOURCE: ANPP (P1) | TYPE: RCP | SECTION: 4.2 Posologie et mode d'administration]"
    content = (
        "Cette présentation contient 1000 mg de paracétamol par comprimé. "
        "La posologie usuelle chez l'adulte et l'enfant de plus de 50 kg est de 1 comprimé (1000 mg) "
        "par prise, à renouveler en cas de besoin au bout de 4 heures minimum sans dépasser 3000 mg par jour."
    )
    full_text = f"{header}\n\n{content}"

    chunk = DrugChunk(
        chunk_id="chk_anpp_posologie_1_sample01",
        text=full_text,
        content=content,
        header=header,
        metadata={
            "brand": "DOLIPRANE",
            "dci": "PARACÉTAMOL",
            "dosage": "1000 mg",
            "form": "comprimé",
            "source": "anpp",
            "source_priority": 1,
            "doc_type": "rcp",
            "section_category": "posology",
            "section_title": "Posologie et mode d'administration",
            "section_number": "4.2",
            "dossier": "01_paracetamol",
        },
    )

    print(f"\n--- 1. INPUT PHARMACEUTICAL CHUNK ---")
    print(f"Chunk ID:  {chunk.chunk_id}")
    print(f"Header:    {chunk.header}")
    print(f"Content:   {chunk.content}")

    # 2. Embed with BGE-M3
    embedder = BGEM3Embedder()
    output = embedder.encode([chunk.text], return_dense=True, return_sparse=True)
    dense_vec = output.dense[0]
    sparse_vec = output.sparse[0] if output.sparse else {}

    norm = sum(x * x for x in dense_vec) ** 0.5
    preview_dense = [round(v, 4) for v in dense_vec[:8]]

    print(f"\n--- 2. DENSE EMBEDDING VECTOR ---")
    print(f"Model:           BAAI/bge-m3 ({embedder.backend})")
    print(f"Vector Length:   {len(dense_vec)} dimensions")
    print(f"L2 Norm:         {norm:.4f} (normalized unit vector)")
    print(f"Vector Preview:  {preview_dense} ... +{len(dense_vec) - 8} more floats")

    print(f"\n--- 3. SPARSE LEXICAL WEIGHTS (BM25 Equivalent) ---")
    print(f"Total Non-Zero Tokens: {len(sparse_vec)}")

    # Try converting token IDs to token strings
    converted_tokens = embedder.convert_id_to_token([sparse_vec])
    sample_tokens = converted_tokens[0] if (converted_tokens and isinstance(converted_tokens, list)) else sparse_vec

    # Sort tokens by weight descending
    top_tokens = sorted(sample_tokens.items(), key=lambda item: item[1], reverse=True)[:10]
    print("Top 10 Lexical Weights:")
    for tok, weight in top_tokens:
        print(f"  • {tok!r:<20} -> {weight:.4f}")

    # 4. Build Qdrant Point
    store = QdrantVectorStore()
    point = store.build_qdrant_point(chunk, dense_vec, sparse_vec)

    print(f"\n--- 4. QDRANT POINTSTRUCT REPRESENTATION ---")
    print(f"Point ID (UUIDv5): {point.id}")
    print(f"Vectors Stored:    Dense ('{store.embedding_config.dense_vector_name}': {len(dense_vec)}-d) + Sparse ('{store.embedding_config.sparse_vector_name}': {len(sparse_vec)} tokens)")
    print(f"Payload Keys:      {list(point.payload.keys())}")
    print("Sample Payload Fields:")
    for k in ["brand", "dci", "source", "source_priority", "section_category", "dosage"]:
        print(f"  • {k:<18}: {point.payload.get(k)}")

    print("=" * 70)


if __name__ == "__main__":
    print("=" * 70)
    print("PHARMEAZOR RAG - BGE-M3 EMBEDDING & QDRANT TEST SUITE")
    print("=" * 70)

    # Run unittest suite
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # If tests succeed, display the sample embedding visualization
    if result.wasSuccessful():
        display_sample_embedding()
    else:
        sys.exit(1)
