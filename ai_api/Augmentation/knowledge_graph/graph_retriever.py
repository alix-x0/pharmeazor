"""
Pharmeazor Knowledge Graph - Graph Retriever
===========================================
Finds entities mentioned in a question, retrieves a bounded subgraph, and
formats sourced graph facts for use alongside vector-retrieved passages.

The retriever never builds the corpus graph implicitly. Call build_from_corpus
explicitly or pass/load a prepared GraphBuilder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Union

from ai_api.Augmentation.knowledge_graph.graph_builder import (
    DEFAULT_GRAPH_PATH,
    GraphBuilder,
    build_knowledge_graph,
    load_knowledge_graph,
)
from ai_api.Augmentation.knowledge_graph.ontology import EntityType, KGEntity, RelationType


def _clean_string_list(value: Any) -> List[str]:
    """Convert a string or iterable of strings into a stable, nonempty list."""
    if value is None:
        return []
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, (list, tuple, set)):
        return []
    if isinstance(values, set):
        values = sorted(values, key=str)

    result: List[str] = []
    seen: Set[str] = set()
    for item in values:
        clean = str(item).strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


@dataclass
class GraphFact:
    """One directed, provenance-carrying fact selected from the graph."""

    subject_id: str
    subject: str
    subject_type: str
    relation_type: str
    object_id: str
    object: str
    object_type: str
    description: str = ""
    confidence: float = 1.0
    source_docs: List[str] = field(default_factory=list)
    source_chunk_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "subject": self.subject,
            "subject_type": self.subject_type,
            "relation_type": self.relation_type,
            "object_id": self.object_id,
            "object": self.object,
            "object_type": self.object_type,
            "description": self.description,
            "confidence": self.confidence,
            "source_docs": list(self.source_docs),
            "source_chunk_ids": list(self.source_chunk_ids),
        }

    def to_context_line(self) -> str:
        """Format this fact as concise context while retaining its citations."""
        line = f"- ({self.subject}) --[{self.relation_type}]--> ({self.object})"
        if self.description:
            line += f": {self.description}"

        provenance = list(self.source_docs)
        if self.source_chunk_ids:
            provenance.extend(f"chunk:{chunk_id}" for chunk_id in self.source_chunk_ids)
        if provenance:
            line += f" [Sources: {', '.join(provenance[:5])}]"
        return line


@dataclass
class GraphRetrievalResult:
    """Structured output from a GraphRetriever query."""

    query: str
    status: str
    matched_entities: List[KGEntity] = field(default_factory=list)
    facts: List[GraphFact] = field(default_factory=list)
    context: str = ""
    source_docs: List[str] = field(default_factory=list)
    subgraph_nodes: int = 0
    subgraph_edges: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "status": self.status,
            "matched_entities": [entity.to_dict() for entity in self.matched_entities],
            "facts": [fact.to_dict() for fact in self.facts],
            "context": self.context,
            "source_docs": list(self.source_docs),
            "subgraph_nodes": self.subgraph_nodes,
            "subgraph_edges": self.subgraph_edges,
        }


class GraphRetriever:
    """
    Retrieves a bounded graph neighborhood for entities found in a question.

    A persisted graph is loaded when graph_path exists. If it does not, an
    empty builder is used; corpus construction remains an explicit call to
    build_from_corpus so API requests cannot unexpectedly scan the corpus.
    """

    def __init__(
        self,
        builder: Optional[GraphBuilder] = None,
        graph_path: Optional[Union[str, Path]] = None,
        confidence_threshold: float = 0.0,
        load_if_available: bool = True,
    ):
        self.graph_path = Path(graph_path) if graph_path is not None else DEFAULT_GRAPH_PATH
        self.confidence_threshold = confidence_threshold

        if builder is not None:
            self.builder = builder
        elif load_if_available and self.graph_path.is_file():
            self.builder = load_knowledge_graph(
                self.graph_path,
                confidence_threshold=confidence_threshold,
            )
        else:
            self.builder = GraphBuilder(confidence_threshold=confidence_threshold)

    @property
    def is_ready(self) -> bool:
        """Whether an in-memory graph with at least one entity is available."""
        return self.builder.graph.number_of_nodes() > 0

    def build_from_corpus(
        self,
        data_dir: Optional[Union[str, Path]] = None,
        dossiers: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        doc_types: Optional[List[str]] = None,
        max_docs: Optional[int] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """Build a fresh graph from the corpus and optionally persist it."""
        self.builder = build_knowledge_graph(
            data_dir=data_dir,
            dossiers=dossiers,
            sources=sources,
            doc_types=doc_types,
            max_docs=max_docs,
            confidence_threshold=self.confidence_threshold,
            save_path=self.graph_path if persist else None,
        )
        return self.builder.get_statistics()

    def load(self, graph_path: Optional[Union[str, Path]] = None) -> GraphBuilder:
        """Load a previously persisted graph into this retriever."""
        if graph_path is not None:
            self.graph_path = Path(graph_path)
        self.builder = load_knowledge_graph(
            self.graph_path,
            confidence_threshold=self.confidence_threshold,
        )
        return self.builder

    def save(self, graph_path: Optional[Union[str, Path]] = None) -> Path:
        """Persist the current graph and return the saved path."""
        if graph_path is not None:
            self.graph_path = Path(graph_path)
        return self.builder.save(self.graph_path)

    def retrieve(
        self,
        query: str,
        *,
        max_hops: int = 1,
        relation_types: Optional[Sequence[Union[RelationType, str]]] = None,
        entity_types: Optional[Sequence[Union[EntityType, str]]] = None,
        direction: str = "both",
        max_entities: int = 5,
        max_nodes: int = 50,
        max_facts: int = 30,
        min_confidence: float = 0.0,
        require_provenance: bool = True,
    ) -> GraphRetrievalResult:
        """
        Find query entities and return their sourced graph neighborhood.

        require_provenance defaults to true so unsourced graph edges are
        excluded from the context intended for evidence-grounded answers.
        """
        question = (query or "").strip()
        if not question:
            return GraphRetrievalResult(query="", status="empty_query")
        if max_hops < 0:
            raise ValueError("max_hops must be zero or greater")
        if max_entities <= 0 or max_nodes <= 0 or max_facts <= 0:
            raise ValueError("max_entities, max_nodes, and max_facts must be positive")
        if direction not in {"in", "out", "both"}:
            raise ValueError("direction must be 'in', 'out', or 'both'")
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0.0 and 1.0")

        if not self.is_ready:
            return GraphRetrievalResult(query=question, status="empty_graph")

        matched = self.builder.extract_entities_from_query(
            question,
            entity_types=entity_types,
            limit=max_entities,
        )
        if not matched:
            return GraphRetrievalResult(query=question, status="no_entity_match")

        subgraph = self.builder.get_subgraph(
            seed_ids=[entity.id for entity in matched],
            max_hops=max_hops,
            relation_types=relation_types,
            direction=direction,
            max_nodes=max_nodes,
        )

        facts: List[GraphFact] = []
        for subject_id, object_id, _edge_key, edge in subgraph.edges(keys=True, data=True):
            confidence = float(edge.get("confidence", 1.0))
            if confidence < min_confidence:
                continue

            metadata = edge.get("metadata")
            metadata = metadata if isinstance(metadata, dict) else {}
            source_docs = _clean_string_list(edge.get("source_docs"))
            if not source_docs:
                source_docs = _clean_string_list(metadata.get("source_docs"))
            if not source_docs:
                source_docs = _clean_string_list(edge.get("source_doc"))

            source_chunks = _clean_string_list(edge.get("source_chunk_ids"))
            if not source_chunks:
                source_chunks = _clean_string_list(metadata.get("source_chunk_ids"))
            if not source_chunks:
                source_chunks = _clean_string_list(edge.get("source_chunk_id"))

            if require_provenance and not (source_docs or source_chunks):
                continue

            subject_attrs = subgraph.nodes[subject_id]
            object_attrs = subgraph.nodes[object_id]
            relation_type = edge.get("relation_type", "")
            if isinstance(relation_type, RelationType):
                relation_type = relation_type.value

            facts.append(
                GraphFact(
                    subject_id=str(subject_id),
                    subject=str(subject_attrs.get("name", subject_id)),
                    subject_type=str(subject_attrs.get("entity_type", "")),
                    relation_type=str(relation_type),
                    object_id=str(object_id),
                    object=str(object_attrs.get("name", object_id)),
                    object_type=str(object_attrs.get("entity_type", "")),
                    description=str(edge.get("description", "") or ""),
                    confidence=confidence,
                    source_docs=source_docs,
                    source_chunk_ids=source_chunks,
                )
            )

        facts.sort(
            key=lambda fact: (
                -fact.confidence,
                fact.relation_type,
                fact.subject_id,
                fact.object_id,
            )
        )
        facts = facts[:max_facts]
        context = "\n".join(fact.to_context_line() for fact in facts)

        all_sources: List[str] = []
        seen_sources: Set[str] = set()
        for fact in facts:
            for source in fact.source_docs:
                if source not in seen_sources:
                    seen_sources.add(source)
                    all_sources.append(source)

        if facts:
            status = "ok"
        elif subgraph.number_of_edges() > 0:
            status = "no_eligible_facts"
        else:
            status = "no_relations_found"

        return GraphRetrievalResult(
            query=question,
            status=status,
            matched_entities=matched,
            facts=facts,
            context=context,
            source_docs=all_sources,
            subgraph_nodes=subgraph.number_of_nodes(),
            subgraph_edges=subgraph.number_of_edges(),
        )

    def retrieve_context(self, query: str, **kwargs: Any) -> str:
        """Convenience method returning only the context string for prompt assembly."""
        return self.retrieve(query, **kwargs).context


__all__ = [
    "GraphFact",
    "GraphRetrievalResult",
    "GraphRetriever",
]
