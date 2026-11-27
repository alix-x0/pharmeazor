"""
Augmentation Subsystem Package
==============================
Enriches and augments retrieved pharmaceutical context with:
- Structured Clinical Knowledge Graph & Ontology (knowledge_graph/)
- Entity and relationship extraction
- GraphRAG factual context injection
"""

from ai_api.Augmentation.knowledge_graph.ontology import (
    EntityType,
    KGEntity,
    KGRelation,
    RelationType,
)

__all__ = [
    "EntityType",
    "RelationType",
    "KGEntity",
    "KGRelation",
]
