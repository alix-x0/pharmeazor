"""
Pharmeazor RAG System - BGE-M3 Multilingual Embedding Engine
============================================================
Handles dense and sparse lexical vector generation using BAAI/bge-m3.

Features:
- Dense vector generation (1024-d, normalized unit vectors).
- Sparse lexical weight generation (BM25 equivalent, token_id -> weight).
- Query encoding without prompt instruction prefix.
- Token decoding helper (convert_id_to_token).
- Fallbacks for environments with FlagEmbedding, sentence-transformers, or simulated testing.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)

# Check optional dependencies
_FLAG_EMBEDDING_AVAILABLE = False
_SENTENCE_TRANSFORMERS_AVAILABLE = False

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
class EmbeddingOutput:
    """Container for multi-function vectors returned by the embedder."""
    dense: List[List[float]]                          # Shape: (N, 1024)
    sparse: Optional[List[Dict[int, float]]] = None   # List of {token_id: weight} dictionaries
    colbert: Optional[List[Any]] = None               # Optional ColBERT representations


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
        """
        self._init_model()

        if isinstance(texts, str):
            text_list = [texts]
        else:
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
                    clean_dict: Dict[int, float] = {}
                    for k, v in weights.items():
                        try:
                            clean_dict[int(k)] = float(v)
                        except (ValueError, TypeError):
                            token_hash = int(hashlib.md5(str(k).encode("utf-8")).hexdigest()[:8], 16)
                            clean_dict[token_hash] = float(v)
                    sparse_vecs.append(clean_dict)

            return EmbeddingOutput(dense=dense_vecs, sparse=sparse_vecs)

        # Case 2: SentenceTransformer fallback
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

        # Case 3: Offline Simulated Embedder
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
            val = ((byte_val ^ (i & 0xFF)) / 128.0) - 1.0
            vector.append(val)
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 0:
            vector = [round(x / norm, 6) for x in vector]
        return vector

    def _compute_pseudo_sparse(self, text: str) -> Dict[int, float]:
        """Generates a deterministic sparse token weight map."""
        words = [w.strip().lower() for w in text.split() if len(w.strip()) > 2]
        counts: Dict[str, int] = {}
        for w in words:
            counts[w] = counts.get(w, 0) + 1

        sparse_dict: Dict[int, float] = {}
        for w, c in counts.items():
            token_id = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:6], 16)
            weight = round(min(1.0, 0.15 + (c * 0.1)), 4)
            sparse_dict[token_id] = weight
        return sparse_dict


default_embedder = BGEM3Embedder()


def embed_texts(texts: Union[str, List[str]], **kwargs: Any) -> EmbeddingOutput:
    """Convenience function to generate BGE-M3 embeddings."""
    return default_embedder.encode(texts, **kwargs)


def embed_query(query: str) -> Tuple[List[float], Dict[int, float]]:
    """Convenience function to encode a user query into dense + sparse vectors."""
    return default_embedder.encode_query(query)
