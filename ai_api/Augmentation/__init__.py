"""
Augmentation Subsystem Package
==============================
Enriches and augments retrieved pharmaceutical context with:
- Structured Clinical Knowledge Graph & Ontology (knowledge_graph/)
- Entity and relationship extraction
- GraphRAG factual context injection
"""

from ai_api.Augmentation.knowledge_graph.entity_extractor import (
    EntityExtractor,
    make_entity_id,
    normalize_string,
)
from ai_api.Augmentation.knowledge_graph.ontology import (
    EntityType,
    KGEntity,
    KGRelation,
    RelationType,
)
from ai_api.Augmentation.knowledge_graph.relationship_extractor import (
    ExtractionResult,
    RelationshipExtractor,
    default_extractor,
    extract_relationships_from_corpus,
    extract_relationships_from_document,
)

__all__ = [
    "EntityType",
    "RelationType",
    "KGEntity",
    "KGRelation",
    "EntityExtractor",
    "RelationshipExtractor",
    "ExtractionResult",
    "default_extractor",
    "extract_relationships_from_document",
    "extract_relationships_from_corpus",
    "make_entity_id",
    "normalize_string",
]
