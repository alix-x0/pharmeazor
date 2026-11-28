"""
Pharmeazor Knowledge Graph - Graph Builder
==========================================
Constructs, merges, queries, and persists a NetworkX-based Pharmaceutical
Knowledge Graph from extracted clinical entities and relationships.

Core Capabilities:
------------------
1. Multi-Document Graph Construction:
   Ingests ExtractionResult objects, raw monograph dicts, JSON files, or the
   curated corpus (data/outputs_data) into a directed multigraph keyed by
   RelationType.
2. Entity Resolution & Provenance Merging:
   Deduplicates canonical entities across ANPP, BDPM, PharmNet, and DailyMed
   while aggregating aliases, source documents, chunk IDs, and confidence scores.
3. Fast Indexing & Subgraph Extraction (for GraphRetriever):
   Maintains O(1) name/alias and type indices, fuzzy/token entity lookup,
   natural-language query entity matching, multi-hop BFS subgraph extraction,
   and GraphRAG context formatting.
4. Serialization:
   Fast JSON save/load round-trips and optional GraphML export.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

import networkx as nx

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Augmentation.knowledge_graph.entity_extractor import (
    make_entity_id,
    normalize_string,
)
from ai_api.Augmentation.knowledge_graph.ontology import (
    EntityType,
    InteractionSeverity,
    KGEntity,
    KGRelation,
    RelationType,
    SourceAuthority,
)
from ai_api.Augmentation.knowledge_graph.relationship_extractor import (
    DEFAULT_DATA_DIR,
    ExtractionResult,
    RelationshipExtractor,
)
from ai_api.Retrieval.chunking import DrugChunk, chunk_corpus

logger = logging.getLogger(__name__)

DEFAULT_GRAPH_PATH = Path(__file__).resolve().parent / "artifacts" / "pharmeazor_kg.json"

def _source_doc_id(path: Path, root: Optional[Union[str, Path]] = None) -> str:
    """Return a stable corpus-relative source path when the file is in the corpus."""
    resolved = path.resolve()
    roots = [Path(root)] if root is not None else []
    roots.append(DEFAULT_DATA_DIR)
    for candidate in roots:
        try:
            return resolved.relative_to(candidate.resolve()).as_posix()
        except ValueError:
            continue
    return resolved.as_posix()
# Stopwords ignored during full-sentence entity extraction
_QUERY_STOPWORDS: Set[str] = {
    "a", "ai", "ainsi", "all", "and", "as", "at", "au", "aucun", "aucune",
    "aux", "avec", "be", "by", "cas", "ce", "ces", "cet", "cette", "chez",
    "comment", "con", "contre", "dans", "de", "des", "doit", "donc", "dont",
    "dose", "du", "elle", "en", "entre", "est", "et", "etre", "for", "from",
    "generale", "il", "ils", "in", "is", "it", "je", "jour", "jusqu", "l",
    "la", "le", "les", "leur", "leurs", "lors", "ma", "mais", "me", "medicament",
    "medicaments", "mes", "mon", "ne", "ni", "non", "nos", "notre", "nous",
    "of", "on", "or", "ou", "par", "pas", "pendant", "peut", "peuvent", "plus",
    "pour", "prendre", "prise", "prises", "qu", "quand", "que", "quel", "quelle",
    "quelles", "quels", "qui", "regle", "s", "sa", "sans", "se", "ses", "si",
    "sont", "sous", "sur", "ta", "te", "tes", "that", "the", "this", "to",
    "ton", "tous", "tout", "toute", "toutes", "traitement", "un", "une", "vers",
    "vos", "votre", "vous", "with", "y",
}

_ENTITY_PREFIX_MAP: List[Tuple[str, EntityType]] = sorted(
    [(f"{et.value.lower()}_", et) for et in EntityType],
    key=lambda item: -len(item[0]),
)


def _infer_entity_type_from_id(entity_id: str) -> EntityType:
    """Infers EntityType from a canonical entity ID prefix."""
    lowered = entity_id.lower()
    for prefix, et in _ENTITY_PREFIX_MAP:
        if lowered.startswith(prefix):
            return et
    return EntityType.DRUG


def _merge_unique_list(existing: List[str], incoming: Iterable[str]) -> List[str]:
    """Merges string lists while preserving insertion order and removing blanks."""
    seen: Set[str] = set()
    merged: List[str] = []
    for val in list(existing) + list(incoming):
        clean = str(val).strip()
        if clean and clean not in seen:
            seen.add(clean)
            merged.append(clean)
    return merged


def _merge_metadata(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Safely merges metadata dictionaries, accumulating multi-document provenance."""
    merged = dict(existing)
    multi_value_keys = {
        "source": "sources",
        "source_url": "source_urls",
        "dossier": "dossiers",
        "doc_type": "doc_types",
        "drug_id": "drug_ids",
    }

    for k, v in incoming.items():
        if v is None or v == "":
            continue
        if k not in merged or merged[k] in (None, ""):
            merged[k] = v
        elif merged[k] != v and k in multi_value_keys:
            plural_key = multi_value_keys[k]
            acc = list(merged.get(plural_key, []))
            if merged[k] not in acc:
                acc.append(merged[k])
            if v not in acc:
                acc.append(v)
            merged[plural_key] = acc

        if k in multi_value_keys:
            plural_key = multi_value_keys[k]
            if plural_key in merged:
                acc = list(merged[plural_key])
                if v not in acc:
                    acc.append(v)
                    merged[plural_key] = acc
    return merged


@dataclass
class GraphBuildStats:
    """Summary metrics recorded during knowledge graph construction."""

    documents_processed: int = 0
    documents_failed: int = 0
    chunks_processed: int = 0
    entities_added: int = 0
    entities_merged: int = 0
    relations_added: int = 0
    relations_merged: int = 0
    relations_skipped_low_confidence: int = 0
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "documents_processed": self.documents_processed,
            "documents_failed": self.documents_failed,
            "chunks_processed": self.chunks_processed,
            "entities_added": self.entities_added,
            "entities_merged": self.entities_merged,
            "relations_added": self.relations_added,
            "relations_merged": self.relations_merged,
            "relations_skipped_low_confidence": self.relations_skipped_low_confidence,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GraphBuildStats:
        return cls(
            documents_processed=int(data.get("documents_processed", 0)),
            documents_failed=int(data.get("documents_failed", 0)),
            chunks_processed=int(data.get("chunks_processed", 0)),
            entities_added=int(data.get("entities_added", 0)),
            entities_merged=int(data.get("entities_merged", 0)),
            relations_added=int(data.get("relations_added", 0)),
            relations_merged=int(data.get("relations_merged", 0)),
            relations_skipped_low_confidence=int(data.get("relations_skipped_low_confidence", 0)),
            elapsed_seconds=float(data.get("elapsed_seconds", 0.0)),
        )


class GraphBuilder:
    """
    Builds and manages the Pharmeazor Pharmaceutical Knowledge Graph using NetworkX.

    The underlying graph is a `networkx.MultiDiGraph` where:
    - Nodes represent canonical `KGEntity` instances keyed by `entity.id`.
    - Directed edges are keyed by `(source_id, target_id, relation_type.value)` so
      different clinical relation types between the same two entities coexist cleanly,
      while identical triples merge their supporting `source_docs` and confidence.
    """

    def __init__(
        self,
        extractor: Optional[RelationshipExtractor] = None,
        confidence_threshold: float = 0.0,
        graph: Optional[nx.MultiDiGraph] = None,
    ):
        self.extractor = extractor or RelationshipExtractor()
        self.confidence_threshold = confidence_threshold
        self.graph: nx.MultiDiGraph = graph if graph is not None else nx.MultiDiGraph()
        self.stats = GraphBuildStats()

        # Fast in-memory lookup indices kept synchronized with `self.graph`
        self._entities: Dict[str, KGEntity] = {}
        self._name_index: Dict[str, Set[str]] = {}
        self._drug_prefix_index: Dict[str, Set[str]] = {}
        self._type_index: Dict[EntityType, Set[str]] = {et: set() for et in EntityType}

        if len(self.graph) > 0:
            self._rebuild_indices()

    # ------------------------------------------------------------------
    # Index & Node/Edge Management
    # ------------------------------------------------------------------

    def _index_entity(self, entity: KGEntity) -> None:
        self._entities[entity.id] = entity
        self._type_index[entity.entity_type].add(entity.id)

        candidates = [entity.name] + list(entity.aliases)
        for text in candidates:
            norm = normalize_string(text)
            if norm:
                self._name_index.setdefault(norm, set()).add(entity.id)
                if entity.entity_type in {EntityType.DRUG, EntityType.ACTIVE_INGREDIENT}:
                    tokens = norm.split("_")
                    for length in range(2, min(len(tokens), 12) + 1):
                        prefix = "_".join(tokens[:length])
                        self._drug_prefix_index.setdefault(prefix, set()).add(entity.id)

    def _rebuild_indices(self) -> None:
        self._entities.clear()
        self._name_index.clear()
        self._drug_prefix_index.clear()
        self._type_index = {et: set() for et in EntityType}

        for node_id, attrs in self.graph.nodes(data=True):
            raw_type = attrs.get("entity_type")
            etype = EntityType(raw_type) if raw_type else _infer_entity_type_from_id(str(node_id))
            entity = KGEntity(
                id=str(node_id),
                name=str(attrs.get("name") or node_id),
                entity_type=etype,
                aliases=list(attrs.get("aliases", [])),
                collection_date=attrs.get("collection_date"),
                metadata=dict(attrs.get("metadata", {})),
            )
            self._index_entity(entity)

    def _sync_node_attrs(self, entity: KGEntity) -> None:
        self.graph.add_node(
            entity.id,
            id=entity.id,
            name=entity.name,
            entity_type=entity.entity_type.value,
            aliases=list(entity.aliases),
            collection_date=entity.collection_date,
            metadata=dict(entity.metadata),
            normalized_name=normalize_string(entity.name),
        )

    def _ensure_node_exists(self, entity_id: str) -> KGEntity:
        if entity_id in self._entities:
            return self._entities[entity_id]

        etype = _infer_entity_type_from_id(entity_id)
        prefix = f"{etype.value.lower()}_"
        fallback_name = entity_id[len(prefix):] if entity_id.lower().startswith(prefix) else entity_id
        fallback_name = fallback_name.replace("_", " ").strip().capitalize() or entity_id

        stub = KGEntity(
            id=entity_id,
            name=fallback_name,
            entity_type=etype,
            aliases=[fallback_name.lower()],
            metadata={"inferred_stub": True},
        )
        return self.add_entity(stub)

    def add_entity(self, entity: KGEntity) -> KGEntity:
        """
        Adds a canonical entity node to the graph, merging aliases and metadata
        if an entity with the same ID already exists.
        """
        if entity.id in self._entities:
            existing = self._entities[entity.id]
            existing.aliases = _merge_unique_list(
                existing.aliases,
                [entity.name] + list(entity.aliases),
            )
            existing.metadata = _merge_metadata(existing.metadata, entity.metadata)
            if entity.collection_date and (
                not existing.collection_date or entity.collection_date > existing.collection_date
            ):
                existing.collection_date = entity.collection_date
            # Clear inferred stub marker if real entity data arrives
            if existing.metadata.get("inferred_stub") and not entity.metadata.get("inferred_stub"):
                existing.name = entity.name
                existing.metadata.pop("inferred_stub", None)

            self._sync_node_attrs(existing)
            self._index_entity(existing)
            self.stats.entities_merged += 1
            return existing

        stored = KGEntity(
            id=entity.id,
            name=entity.name,
            entity_type=entity.entity_type,
            aliases=_merge_unique_list([entity.name], entity.aliases),
            collection_date=entity.collection_date,
            metadata=dict(entity.metadata),
        )
        self._sync_node_attrs(stored)
        self._index_entity(stored)
        self.stats.entities_added += 1
        return stored

    def add_relation(self, relation: KGRelation) -> bool:
        """
        Adds a directed clinical relationship to the MultiDiGraph.

        Edges are keyed by `relation.relation_type.value` so multiple relation
        types between the same two entities remain distinct, while repeated
        triples merge provenance (`source_docs`, `source_chunk_ids`) and take
        the maximum confidence score.
        """
        if relation.confidence < self.confidence_threshold:
            self.stats.relations_skipped_low_confidence += 1
            return False

        self._ensure_node_exists(relation.source_id)
        self._ensure_node_exists(relation.target_id)

        edge_key = relation.relation_type.value
        if self.graph.has_edge(relation.source_id, relation.target_id, key=edge_key):
            edge_data = self.graph[relation.source_id][relation.target_id][edge_key]
            edge_data["confidence"] = max(float(edge_data.get("confidence", 0.0)), relation.confidence)

            if relation.description and len(relation.description) > len(edge_data.get("description", "")):
                edge_data["description"] = relation.description

            src_docs = list(edge_data.get("source_docs", []))
            if relation.source_doc and relation.source_doc not in src_docs:
                src_docs.append(relation.source_doc)
            edge_data["source_docs"] = src_docs
            if not edge_data.get("source_doc") and relation.source_doc:
                edge_data["source_doc"] = relation.source_doc

            chunk_ids = list(edge_data.get("source_chunk_ids", []))
            if relation.source_chunk_id and relation.source_chunk_id not in chunk_ids:
                chunk_ids.append(relation.source_chunk_id)
            edge_data["source_chunk_ids"] = chunk_ids
            if not edge_data.get("source_chunk_id") and relation.source_chunk_id:
                edge_data["source_chunk_id"] = relation.source_chunk_id

            edge_meta = _merge_metadata(edge_data.get("metadata", {}), relation.metadata)
            edge_meta["source_docs"] = src_docs
            if chunk_ids:
                edge_meta["source_chunk_ids"] = chunk_ids
            edge_data["metadata"] = edge_meta

            # Reconcile source authority (lower int = higher trust)
            if relation.source_authority is not None:
                existing_auth = edge_data.get("source_authority")
                if existing_auth is None or relation.source_authority.value < int(existing_auth):
                    edge_data["source_authority"] = relation.source_authority.value
            if relation.collection_date and (
                not edge_data.get("collection_date")
                or relation.collection_date > str(edge_data["collection_date"])
            ):
                edge_data["collection_date"] = relation.collection_date
            if relation.severity is not None and not edge_data.get("severity"):
                edge_data["severity"] = relation.severity.value

            self.stats.relations_merged += 1
            return True

        source_docs = [relation.source_doc] if relation.source_doc else []
        source_chunk_ids = [relation.source_chunk_id] if relation.source_chunk_id else []
        edge_meta = dict(relation.metadata)
        if source_docs:
            edge_meta["source_docs"] = source_docs
        if source_chunk_ids:
            edge_meta["source_chunk_ids"] = source_chunk_ids

        self.graph.add_edge(
            relation.source_id,
            relation.target_id,
            key=edge_key,
            relation_type=relation.relation_type.value,
            description=relation.description,
            source_doc=relation.source_doc,
            source_docs=source_docs,
            source_chunk_id=relation.source_chunk_id,
            source_chunk_ids=source_chunk_ids,
            source_authority=(
                relation.source_authority.value if relation.source_authority is not None else None
            ),
            collection_date=relation.collection_date,
            severity=relation.severity.value if relation.severity is not None else None,
            confidence=relation.confidence,
            metadata=edge_meta,
        )
        self.stats.relations_added += 1
        return True

    # ------------------------------------------------------------------
    # Graph Construction Pipelines
    # ------------------------------------------------------------------

    def add_extraction_result(
        self,
        result: ExtractionResult,
        dossier: Optional[str] = None,
    ) -> None:
        """Ingests all entities and relations from an ExtractionResult."""
        for entity in result.entities:
            if dossier and not entity.metadata.get("dossier"):
                entity = replace(entity, metadata={**entity.metadata, "dossier": dossier})
            self.add_entity(entity)

        for relation in result.relations:
            if dossier and not relation.metadata.get("dossier"):
                relation = replace(relation, metadata={**relation.metadata, "dossier": dossier})
            self.add_relation(relation)

    def add_document(
        self,
        doc: Dict[str, Any],
        doc_id: Optional[str] = None,
        dossier: Optional[str] = None,
        source_chunk_id: Optional[str] = None,
        count_document: bool = True,
    ) -> ExtractionResult:
        """Extracts entities and relations from one monograph dict and adds them."""
        target_doc = doc
        if dossier and not doc.get("dossier"):
            target_doc = {**doc, "dossier": dossier}

        result = self.extractor.extract_from_document(target_doc, doc_id=doc_id)
        provenance = {
            key: value
            for key, value in {
                "source": doc.get("source"),
                "source_url": doc.get("url") or doc.get("source_url"),
                "doc_type": doc.get("doc_type"),
            }.items()
            if value not in (None, "")
        }
        if provenance:
            result = ExtractionResult(
                entities=result.entities,
                relations=[
                    replace(
                        relation,
                        source_chunk_id=source_chunk_id or relation.source_chunk_id,
                        metadata={**relation.metadata, **provenance},
                    )
                    for relation in result.relations
                ],
            )
        elif source_chunk_id:
            result = ExtractionResult(
                entities=result.entities,
                relations=[
                    replace(relation, source_chunk_id=source_chunk_id)
                    for relation in result.relations
                ],
            )
        self.add_extraction_result(result, dossier=dossier or doc.get("dossier"))
        if count_document:
            self.stats.documents_processed += 1
        return result

    def add_chunk(self, chunk: DrugChunk) -> ExtractionResult:
        """Extracts grounded graph facts from one clinical chunk."""
        metadata = chunk.metadata
        dossier = str(metadata.get("dossier") or "")
        file_name = str(metadata.get("file_name") or chunk.chunk_id)
        source_doc = "/".join(part.strip("/") for part in (dossier, file_name) if part)

        source = str(metadata.get("source") or "").lower()
        authority_by_source = {
            "anpp": SourceAuthority.ANPP_RCP,
            "nomenclature": SourceAuthority.NOMENCLATURE_OFFICIELLE,
            "bdpm": SourceAuthority.INSTITUTIONNEL_ETRANGER,
            "dailymed": SourceAuthority.INSTITUTIONNEL_ETRANGER,
            "pharmnet": SourceAuthority.PROFESSIONNEL_ALGERIEN,
        }
        source_authority = metadata.get("source_authority") or authority_by_source.get(source)

        doc = {
            "drug_id": metadata.get("drug_id"),
            "brand": metadata.get("brand", ""),
            "dci": metadata.get("dci", ""),
            "lab": metadata.get("lab", ""),
            "form": metadata.get("form", ""),
            "dosage": metadata.get("dosage", ""),
            "source": source,
            "source_priority": metadata.get("source_priority"),
            "source_authority": source_authority,
            "doc_type": metadata.get("doc_type", ""),
            "url": metadata.get("url", ""),
            "dossier": dossier,
            "file_name": file_name,
            "collection_date": metadata.get("collection_date"),
            "sections": [
                {
                    "key": metadata.get("section_key", ""),
                    "number": metadata.get("section_number", ""),
                    "title": metadata.get("section_title", ""),
                    "text": chunk.content,
                }
            ],
        }
        self.stats.chunks_processed += 1
        return self.add_document(
            doc,
            doc_id=source_doc,
            dossier=dossier,
            source_chunk_id=chunk.chunk_id,
            count_document=False,
        )

    def build_from_chunks(self, chunks: Iterable[DrugChunk]) -> nx.MultiDiGraph:
        """Builds the graph from pre-chunked clinical documents."""
        start = time.time()
        source_docs: Set[str] = set()
        for chunk in chunks:
            metadata = chunk.metadata
            dossier = str(metadata.get("dossier") or "")
            file_name = str(metadata.get("file_name") or chunk.chunk_id)
            source_docs.add("/".join(part.strip("/") for part in (dossier, file_name) if part))
            self.add_chunk(chunk)

        self.stats.documents_processed += len(source_docs)
        self.stats.elapsed_seconds += time.time() - start
        return self.graph

    def build_from_chunked_corpus(
        self,
        data_dir: Optional[Union[str, Path]] = None,
        dossier: Optional[str] = None,
        sources: Optional[List[str]] = None,
        drug_ids: Optional[List[int]] = None,
        doc_type: Optional[str] = None,
        brand: Optional[str] = None,
        dci: Optional[str] = None,
        max_docs: Optional[int] = None,
    ) -> nx.MultiDiGraph:
        """Chunks the curated corpus and builds a provenance-linked graph."""
        chunks = chunk_corpus(
            data_dir=data_dir,
            dossier=dossier,
            sources=sources,
            drug_ids=drug_ids,
            doc_type=doc_type,
            brand=brand,
            dci=dci,
            max_docs=max_docs,
        )
        return self.build_from_chunks(chunks)

    def build_from_results(self, results: Iterable[ExtractionResult]) -> nx.MultiDiGraph:
        """Builds/updates the graph from an iterable of ExtractionResult objects."""
        start = time.time()
        for res in results:
            self.add_extraction_result(res)
        self.stats.elapsed_seconds += time.time() - start
        return self.graph

    def build_from_files(self, file_paths: Iterable[Union[str, Path]]) -> nx.MultiDiGraph:
        """Builds/updates the graph from specific monograph JSON file paths."""
        start = time.time()
        for path_like in file_paths:
            fpath = Path(path_like)
            if not fpath.exists():
                logger.warning("File not found, skipping: %s", fpath)
                self.stats.documents_failed += 1
                continue
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    doc = json.load(f)
                dossier = fpath.parent.parent.name if len(fpath.parts) >= 3 else None
                self.add_document(doc, doc_id=_source_doc_id(fpath), dossier=dossier)
            except Exception as exc:
                logger.warning("Failed processing %s: %s", fpath, exc)
                self.stats.documents_failed += 1
        self.stats.elapsed_seconds += time.time() - start
        return self.graph

    def build_from_corpus(
        self,
        data_dir: Optional[Union[str, Path]] = None,
        dossiers: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        doc_types: Optional[List[str]] = None,
        max_docs: Optional[int] = None,
    ) -> nx.MultiDiGraph:
        """
        Streams monographs from the curated corpus directory and constructs the graph.

        Args:
            data_dir: Root directory containing DCI dossier folders (defaults to data/outputs_data).
            dossiers: Optional substring filter for DCI dossier names (e.g. ['01_paracetamol']).
            sources: Optional source filter (e.g. ['anpp', 'bdpm']).
            doc_types: Optional document type filter (e.g. ['rcp', 'notice']).
            max_docs: Optional cap on number of monographs processed.
        """
        root = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        if not root.exists():
            raise FileNotFoundError(f"Corpus directory not found: {root}")

        start = time.time()
        norm_sources = {s.lower() for s in sources} if sources else None
        norm_doc_types = {d.lower() for d in doc_types} if doc_types else None

        json_files = sorted(root.glob("*/*/*.json"))
        processed_here = 0

        for fpath in json_files:
            if fpath.name.startswith("_"):
                continue

            file_dossier = fpath.parent.parent.name if len(fpath.parts) >= 3 else ""
            if dossiers and not any(d.lower() in file_dossier.lower() for d in dossiers):
                continue

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    doc = json.load(f)

                if norm_sources and str(doc.get("source", "")).lower() not in norm_sources:
                    continue
                if norm_doc_types and str(doc.get("doc_type", "")).lower() not in norm_doc_types:
                    continue

                self.add_document(
                    doc,
                    doc_id=_source_doc_id(fpath, root=root),
                    dossier=file_dossier,
                )
                processed_here += 1
                if max_docs and processed_here >= max_docs:
                    break
            except Exception as exc:
                logger.warning("Error building graph from %s: %s", fpath, exc)
                self.stats.documents_failed += 1

        self.stats.elapsed_seconds += time.time() - start
        return self.graph

    # ------------------------------------------------------------------
    # Query, Traversal & Subgraph Retrieval Helpers (for GraphRetriever)
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_entity_type(entity_type: Optional[Union[EntityType, str]]) -> Optional[EntityType]:
        if entity_type is None:
            return None
        return entity_type if isinstance(entity_type, EntityType) else EntityType(str(entity_type))

    @staticmethod
    def _coerce_relation_type(relation_type: Union[RelationType, str]) -> RelationType:
        return relation_type if isinstance(relation_type, RelationType) else RelationType(str(relation_type))

    def has_entity(self, entity_id: str) -> bool:
        return entity_id in self._entities

    def get_entity(self, entity_id: str) -> Optional[KGEntity]:
        return self._entities.get(entity_id)

    def get_entities_by_type(self, entity_type: Union[EntityType, str]) -> List[KGEntity]:
        etype = self._coerce_entity_type(entity_type)
        assert etype is not None
        return [self._entities[eid] for eid in self._type_index.get(etype, set()) if eid in self._entities]

    def find_entities(
        self,
        query: str,
        entity_type: Optional[Union[EntityType, str]] = None,
        limit: int = 10,
    ) -> List[KGEntity]:
        """
        Resolves a surface string (brand, DCI, symptom, lab, etc.) to ranked KGEntity nodes.
        Combines exact ID, exact normalized name/alias, substring, and token overlap scoring.
        """
        if not query or limit <= 0:
            return []

        target_type = self._coerce_entity_type(entity_type)
        stripped = query.strip()

        # Fast-path exact ID match
        if stripped in self._entities:
            ent = self._entities[stripped]
            if target_type is None or ent.entity_type == target_type:
                return [ent]

        norm_q = normalize_string(stripped)
        if not norm_q:
            return []

        q_tokens = {t for t in norm_q.split("_") if len(t) >= 2}
        pool_ids: Iterable[str] = (
            self._type_index.get(target_type, set()) if target_type is not None else self._entities.keys()
        )

        exact_ids = self._name_index.get(norm_q, set())
        scored: List[Tuple[float, int, KGEntity]] = []

        for eid in pool_ids:
            ent = self._entities[eid]
            score = 0.0

            if eid in exact_ids:
                score = 100.0
            else:
                norm_name = normalize_string(ent.name)
                if norm_name == norm_q:
                    score = 95.0
                elif norm_name.startswith(norm_q):
                    score = 80.0
                elif norm_q in norm_name:
                    score = 72.0
                elif norm_name and norm_name in norm_q and len(norm_name) >= 3:
                    # e.g. query="DOLIPRANE 1000 mg" contains entity name "doliprane"
                    coverage = len(norm_name) / len(norm_q)
                    score = 65.0 + 15.0 * coverage
                elif q_tokens:
                    ent_tokens = {t for t in norm_name.split("_") if len(t) >= 2}
                    if ent_tokens:
                        overlap = len(q_tokens & ent_tokens)
                        if overlap > 0:
                            score = 50.0 * (overlap / len(q_tokens | ent_tokens))

            if score > 0.0:
                degree = self.graph.degree(eid) if eid in self.graph else 0
                scored.append((score, degree, ent))

        scored.sort(key=lambda item: (item[0], item[1], -len(item[2].name)), reverse=True)
        return [item[2] for item in scored[:limit]]

    def extract_entities_from_query(
        self,
        query: str,
        entity_types: Optional[Sequence[Union[EntityType, str]]] = None,
        limit: int = 10,
    ) -> List[KGEntity]:
        """
        Extracts matching knowledge graph entities mentioned inside a natural-language
        clinical question (e.g. 'dose maximale de DOLIPRANE 1000 mg' -> [DOLIPRANE]).
        """
        norm_q = normalize_string(query)
        if not norm_q:
            return []

        allowed_types: Optional[Set[EntityType]] = (
            {self._coerce_entity_type(t) for t in entity_types if t is not None}  # type: ignore[misc]
            if entity_types
            else None
        )

        raw_tokens = norm_q.split("_")
        filtered_tokens = [t for t in raw_tokens if t and t not in _QUERY_STOPWORDS]

        matched_ids: Dict[str, float] = {}

        # 1. N-gram lookup against normalized name/alias index. Long product
        # names (brand + strength + form) can exceed four tokens.
        for n in range(len(raw_tokens), 0, -1):
            for i in range(len(raw_tokens) - n + 1):
                gram_tokens = raw_tokens[i : i + n]
                if all(t in _QUERY_STOPWORDS or len(t) < 2 for t in gram_tokens):
                    continue
                gram = "_".join(gram_tokens)
                for eid in self._name_index.get(gram, set()):
                    ent = self._entities[eid]
                    if allowed_types and ent.entity_type not in allowed_types:
                        continue
                    score = 100.0 + n * 10.0
                    if eid not in matched_ids or score > matched_ids[eid]:
                        matched_ids[eid] = score

        # 2. Match a query's shortened product name against indexed prefixes,
        # e.g. "AMOXICILLINE KRKA 1 g" against a longer full brand name.
        for n in range(min(len(raw_tokens), 12), 1, -1):
            for i in range(len(raw_tokens) - n + 1):
                gram_tokens = raw_tokens[i : i + n]
                if all(t in _QUERY_STOPWORDS or len(t) < 2 for t in gram_tokens):
                    continue
                gram = "_".join(gram_tokens)
                for eid in self._drug_prefix_index.get(gram, set()):
                    ent = self._entities[eid]
                    if allowed_types and ent.entity_type not in allowed_types:
                        continue
                    score = 100.0 + n * 10.0
                    if eid not in matched_ids or score > matched_ids[eid]:
                        matched_ids[eid] = score

        # 3. Fallback: single filtered keyword token lookup
        for tok in filtered_tokens:
            if len(tok) < 3:
                continue
            for eid in self._name_index.get(tok, set()):
                ent = self._entities[eid]
                if allowed_types and ent.entity_type not in allowed_types:
                    continue
                matched_ids.setdefault(eid, 80.0)

        # 4. Prioritize DRUG and ACTIVE_INGREDIENT entities if scores tie
        def rank_key(eid: str) -> Tuple[float, int, int]:
            ent = self._entities[eid]
            priority = 2 if ent.entity_type in (EntityType.DRUG, EntityType.ACTIVE_INGREDIENT) else 1
            degree = self.graph.degree(eid) if eid in self.graph else 0
            return (matched_ids[eid], priority, degree)

        sorted_ids = sorted(matched_ids.keys(), key=rank_key, reverse=True)
        return [self._entities[eid] for eid in sorted_ids[:limit]]

    def _edge_to_relation(self, source_id: str, target_id: str, edge_data: Dict[str, Any]) -> KGRelation:
        meta = dict(edge_data.get("metadata", {}))
        if edge_data.get("source_docs") and "source_docs" not in meta:
            meta["source_docs"] = list(edge_data["source_docs"])
        if edge_data.get("source_chunk_ids") and "source_chunk_ids" not in meta:
            meta["source_chunk_ids"] = list(edge_data["source_chunk_ids"])

        raw_auth = edge_data.get("source_authority")
        raw_sev = edge_data.get("severity")
        return KGRelation(
            source_id=str(source_id),
            target_id=str(target_id),
            relation_type=RelationType(edge_data["relation_type"]),
            description=str(edge_data.get("description", "")),
            source_chunk_id=edge_data.get("source_chunk_id"),
            source_doc=edge_data.get("source_doc"),
            source_authority=SourceAuthority(raw_auth) if raw_auth is not None else None,
            collection_date=edge_data.get("collection_date"),
            severity=InteractionSeverity(raw_sev) if raw_sev is not None else None,
            confidence=float(edge_data.get("confidence", 1.0)),
            metadata=meta,
        )

    def get_relations(
        self,
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        relation_type: Optional[Union[RelationType, str]] = None,
    ) -> List[KGRelation]:
        """Returns KGRelation objects matching optional source, target, and relation filters."""
        target_rel = self._coerce_relation_type(relation_type) if relation_type is not None else None
        results: List[KGRelation] = []

        if source_id is not None:
            if source_id not in self.graph:
                return []
            edge_iter = self.graph.out_edges(source_id, keys=True, data=True)
        elif target_id is not None:
            if target_id not in self.graph:
                return []
            edge_iter = self.graph.in_edges(target_id, keys=True, data=True)
        else:
            edge_iter = self.graph.edges(keys=True, data=True)

        for u, v, _key, data in edge_iter:
            if source_id is not None and u != source_id:
                continue
            if target_id is not None and v != target_id:
                continue
            if target_rel is not None and data.get("relation_type") != target_rel.value:
                continue
            results.append(self._edge_to_relation(u, v, data))

        return results

    def get_neighbors(
        self,
        entity_id: str,
        relation_types: Optional[Sequence[Union[RelationType, str]]] = None,
        target_types: Optional[Sequence[Union[EntityType, str]]] = None,
        direction: str = "out",
        min_confidence: float = 0.0,
    ) -> List[Tuple[KGRelation, KGEntity]]:
        """
        Retrieves connected (KGRelation, neighbor KGEntity) pairs around `entity_id`.

        Args:
            entity_id: Starting node ID.
            relation_types: Optional whitelist of RelationType values.
            target_types: Optional whitelist of neighbor EntityType values.
            direction: 'out' (outgoing edges), 'in' (incoming edges), or 'both'.
            min_confidence: Minimum edge confidence score.
        """
        if entity_id not in self.graph:
            return []

        allowed_rels: Optional[Set[str]] = (
            {self._coerce_relation_type(r).value for r in relation_types}
            if relation_types
            else None
        )
        allowed_targets: Optional[Set[EntityType]] = (
            {self._coerce_entity_type(t) for t in target_types if t is not None}  # type: ignore[misc]
            if target_types
            else None
        )

        neighbors: List[Tuple[KGRelation, KGEntity]] = []

        if direction in ("out", "both"):
            for u, v, _key, data in self.graph.out_edges(entity_id, keys=True, data=True):
                if allowed_rels and data.get("relation_type") not in allowed_rels:
                    continue
                if float(data.get("confidence", 1.0)) < min_confidence:
                    continue
                neighbor_ent = self._entities.get(v)
                if not neighbor_ent:
                    continue
                if allowed_targets and neighbor_ent.entity_type not in allowed_targets:
                    continue
                neighbors.append((self._edge_to_relation(u, v, data), neighbor_ent))

        if direction in ("in", "both"):
            for u, v, _key, data in self.graph.in_edges(entity_id, keys=True, data=True):
                if allowed_rels and data.get("relation_type") not in allowed_rels:
                    continue
                if float(data.get("confidence", 1.0)) < min_confidence:
                    continue
                neighbor_ent = self._entities.get(u)
                if not neighbor_ent:
                    continue
                if allowed_targets and neighbor_ent.entity_type not in allowed_targets:
                    continue
                neighbors.append((self._edge_to_relation(u, v, data), neighbor_ent))

        neighbors.sort(key=lambda pair: pair[0].confidence, reverse=True)
        return neighbors

    def get_subgraph(
        self,
        seed_ids: Iterable[str],
        max_hops: int = 2,
        relation_types: Optional[Sequence[Union[RelationType, str]]] = None,
        direction: str = "both",
        max_nodes: int = 100,
    ) -> nx.MultiDiGraph:
        """
        Extracts a bounded k-hop ego subgraph around seed entity IDs via BFS.
        """
        valid_seeds = [sid for sid in seed_ids if sid in self.graph]
        if not valid_seeds or max_hops < 0 or max_nodes <= 0:
            return nx.MultiDiGraph()

        allowed_rels: Optional[Set[str]] = (
            {self._coerce_relation_type(r).value for r in relation_types}
            if relation_types
            else None
        )

        visited: List[str] = []
        visited_set: Set[str] = set()
        queue: List[Tuple[str, int]] = []

        for sid in valid_seeds:
            if sid not in visited_set and len(visited) < max_nodes:
                visited_set.add(sid)
                visited.append(sid)
                queue.append((sid, 0))

        head = 0
        while head < len(queue) and len(visited) < max_nodes:
            curr_id, depth = queue[head]
            head += 1
            if depth >= max_hops:
                continue

            next_ids: List[str] = []
            if direction in ("out", "both"):
                for _, v, _k, data in self.graph.out_edges(curr_id, keys=True, data=True):
                    if not allowed_rels or data.get("relation_type") in allowed_rels:
                        next_ids.append(v)
            if direction in ("in", "both"):
                for u, _, _k, data in self.graph.in_edges(curr_id, keys=True, data=True):
                    if not allowed_rels or data.get("relation_type") in allowed_rels:
                        next_ids.append(u)

            for nid in next_ids:
                if nid not in visited_set:
                    visited_set.add(nid)
                    visited.append(nid)
                    queue.append((nid, depth + 1))
                    if len(visited) >= max_nodes:
                        break

        sub: nx.MultiDiGraph = self.graph.subgraph(visited).copy()
        if allowed_rels:
            to_remove = [
                (u, v, k)
                for u, v, k, data in sub.edges(keys=True, data=True)
                if data.get("relation_type") not in allowed_rels
            ]
            sub.remove_edges_from(to_remove)
        return sub

    def format_subgraph_context(
        self,
        subgraph: nx.MultiDiGraph,
        max_triples: int = 50,
    ) -> str:
        """
        Formats a subgraph into structured clinical fact lines with document
        provenance suitable for GraphRAG LLM context injection.
        """
        if len(subgraph) == 0 or subgraph.number_of_edges() == 0:
            return ""

        edges = sorted(
            subgraph.edges(keys=True, data=True),
            key=lambda item: float(item[3].get("confidence", 0.0)),
            reverse=True,
        )[:max_triples]

        lines: List[str] = []
        for u, v, _k, data in edges:
            src_name = subgraph.nodes[u].get("name", u)
            tgt_name = subgraph.nodes[v].get("name", v)
            rel_name = data.get("relation_type", "RELATED_TO")
            desc = data.get("description", "")
            docs = data.get("source_docs") or ([data["source_doc"]] if data.get("source_doc") else [])
            provenance = f" [Sources: {', '.join(docs[:3])}]" if docs else ""

            fact = f"- ({src_name}) --[{rel_name}]--> ({tgt_name})"
            if desc:
                fact += f" : {desc}"
            fact += provenance
            lines.append(fact)

        return "\n".join(lines)

    def get_drug_summary(self, drug_or_dci: str) -> Dict[str, Any]:
        """
        Returns a structured clinical summary for the best-matching DRUG or
        ACTIVE_INGREDIENT entity in the graph.
        """
        matches = self.find_entities(drug_or_dci, entity_type=EntityType.DRUG, limit=1)
        if not matches:
            matches = self.find_entities(drug_or_dci, entity_type=EntityType.ACTIVE_INGREDIENT, limit=1)
        if not matches:
            return {"query": drug_or_dci, "found": False}

        root_ent = matches[0]
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for rel, target_ent in self.get_neighbors(root_ent.id, direction="out"):
            rel_key = rel.relation_type.value
            grouped.setdefault(rel_key, []).append(
                {
                    "entity_id": target_ent.id,
                    "name": target_ent.name,
                    "entity_type": target_ent.entity_type.value,
                    "description": rel.description,
                    "confidence": rel.confidence,
                    "source_docs": rel.metadata.get("source_docs", [rel.source_doc] if rel.source_doc else []),
                }
            )

        return {
            "query": drug_or_dci,
            "found": True,
            "entity": root_ent.to_dict(),
            "relations_by_type": grouped,
        }

    # ------------------------------------------------------------------
    # Statistics & Serialization
    # ------------------------------------------------------------------

    def get_statistics(self) -> Dict[str, Any]:
        """Returns comprehensive graph topology and ontology breakdown metrics."""
        entity_breakdown: Dict[str, int] = {}
        for _, attrs in self.graph.nodes(data=True):
            etype = str(attrs.get("entity_type", "UNKNOWN"))
            entity_breakdown[etype] = entity_breakdown.get(etype, 0) + 1

        relation_breakdown: Dict[str, int] = {}
        for _, _, _, attrs in self.graph.edges(keys=True, data=True):
            rtype = str(attrs.get("relation_type", "UNKNOWN"))
            relation_breakdown[rtype] = relation_breakdown.get(rtype, 0) + 1

        num_nodes = self.graph.number_of_nodes()
        num_edges = self.graph.number_of_edges()
        num_components = nx.number_weakly_connected_components(self.graph) if num_nodes > 0 else 0

        return {
            "total_nodes": num_nodes,
            "total_edges": num_edges,
            "weakly_connected_components": num_components,
            "density": round(nx.density(self.graph), 6) if num_nodes > 1 else 0.0,
            "entity_breakdown": entity_breakdown,
            "relationship_breakdown": relation_breakdown,
            "build_stats": self.stats.to_dict(),
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the entire knowledge graph to a JSON-compatible dictionary."""
        return {
            "version": "1.0.0",
            "build_stats": self.stats.to_dict(),
            "entities": [self._entities[eid].to_dict() for eid in sorted(self._entities.keys())],
            "relations": [r.to_dict() for r in self.get_relations()],
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        confidence_threshold: float = 0.0,
    ) -> GraphBuilder:
        """Reconstructs a GraphBuilder and NetworkX MultiDiGraph from a dictionary."""
        builder = cls(confidence_threshold=confidence_threshold)

        for raw_ent in data.get("entities", []):
            builder.add_entity(KGEntity.from_dict(raw_ent))

        for raw_rel in data.get("relations", []):
            builder.add_relation(KGRelation.from_dict(raw_rel))

        if "build_stats" in data:
            builder.stats = GraphBuildStats.from_dict(data["build_stats"])
        return builder

    def save(self, output_path: Optional[Union[str, Path]] = None) -> Path:
        """Persists the knowledge graph to disk as JSON."""
        out = Path(output_path) if output_path else DEFAULT_GRAPH_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        return out

    @classmethod
    def load(
        cls,
        input_path: Optional[Union[str, Path]] = None,
        confidence_threshold: float = 0.0,
    ) -> GraphBuilder:
        """Loads a persisted JSON knowledge graph from disk."""
        src = Path(input_path) if input_path else DEFAULT_GRAPH_PATH
        if not src.exists():
            raise FileNotFoundError(f"Knowledge graph file not found: {src}")
        with open(src, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data, confidence_threshold=confidence_threshold)

    def export_graphml(self, output_path: Union[str, Path]) -> Path:
        """
        Exports a GraphML-compatible copy of the graph (list/dict attributes
        are JSON-encoded as strings) for external graph visualization tools.
        """
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        export_g = nx.MultiDiGraph()
        for node_id, attrs in self.graph.nodes(data=True):
            clean_attrs = {
                k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else ("" if v is None else v)
                for k, v in attrs.items()
            }
            export_g.add_node(node_id, **clean_attrs)

        for u, v, key, attrs in self.graph.edges(keys=True, data=True):
            clean_attrs = {
                k: json.dumps(val, ensure_ascii=False) if isinstance(val, (list, dict)) else ("" if val is None else val)
                for k, val in attrs.items()
            }
            export_g.add_edge(u, v, key=key, **clean_attrs)

        nx.write_graphml(export_g, str(out))
        return out


# Alias for callers expecting KnowledgeGraphBuilder
KnowledgeGraphBuilder = GraphBuilder


def build_knowledge_graph(
    data_dir: Optional[Union[str, Path]] = None,
    dossiers: Optional[List[str]] = None,
    sources: Optional[List[str]] = None,
    doc_types: Optional[List[str]] = None,
    max_docs: Optional[int] = None,
    confidence_threshold: float = 0.0,
    save_path: Optional[Union[str, Path]] = None,
) -> GraphBuilder:
    """
    Convenience entry point to build (and optionally persist) the Pharmeazor
    Knowledge Graph from the pharmaceutical corpus.
    """
    builder = GraphBuilder(confidence_threshold=confidence_threshold)
    builder.build_from_corpus(
        data_dir=data_dir,
        dossiers=dossiers,
        sources=sources,
        doc_types=doc_types,
        max_docs=max_docs,
    )
    if save_path:
        builder.save(save_path)
    return builder


def load_knowledge_graph(
    input_path: Optional[Union[str, Path]] = None,
    confidence_threshold: float = 0.0,
) -> GraphBuilder:
    """Convenience helper to load a saved GraphBuilder from JSON."""
    return GraphBuilder.load(input_path=input_path, confidence_threshold=confidence_threshold)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Pharmeazor Pharmaceutical Knowledge Graph")
    parser.add_argument("--data-dir", type=str, default=None, help="Path to corpus directory")
    parser.add_argument("--dossiers", nargs="*", default=None, help="Optional DCI dossiers filter")
    parser.add_argument("--sources", nargs="*", default=None, help="Optional sources filter (anpp, bdpm, etc.)")
    parser.add_argument("--max-docs", type=int, default=None, help="Optional max documents to process")
    parser.add_argument("--save", nargs="?", const=str(DEFAULT_GRAPH_PATH), default=None, help="Save KG to JSON path")
    parser.add_argument("--query", type=str, default="DOLIPRANE", help="Sample drug/DCI summary lookup")
    args = parser.parse_args()

    print("=" * 72)
    print("PHARMEAZOR KNOWLEDGE GRAPH BUILDER")
    print("=" * 72)

    kg_builder = build_knowledge_graph(
        data_dir=args.data_dir,
        dossiers=args.dossiers,
        sources=args.sources,
        max_docs=args.max_docs,
        save_path=args.save,
    )

    stats = kg_builder.get_statistics()
    print(f"Nodes      : {stats['total_nodes']}")
    print(f"Edges      : {stats['total_edges']}")
    print(f"Components : {stats['weakly_connected_components']}")
    print(f"Build time : {stats['build_stats']['elapsed_seconds']}s")

    print("\n--- Entity Breakdown ---")
    for etype, cnt in sorted(stats["entity_breakdown"].items(), key=lambda x: -x[1]):
        print(f"  - {etype:<24} : {cnt}")

    print("\n--- Relationship Breakdown ---")
    for rtype, cnt in sorted(stats["relationship_breakdown"].items(), key=lambda x: -x[1]):
        print(f"  - {rtype:<28} : {cnt}")

    if args.save:
        print(f"\nSaved graph to: {args.save}")

    summary = kg_builder.get_drug_summary(args.query)
    if summary.get("found"):
        ent = summary["entity"]
        print(f"\n--- Sample Summary: {ent['name']} ({ent['id']}) ---")
        for rel_name, items in summary["relations_by_type"].items():
            print(f"  * {rel_name}: {len(items)} links")

    print("=" * 72)
