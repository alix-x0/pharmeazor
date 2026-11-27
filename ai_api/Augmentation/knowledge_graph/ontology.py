"""
Pharmeazor Knowledge Graph - Pharmaceutical Ontology & Schema
==============================================================
Defines canonical clinical entity types, relationship types, and data models
for the Pharmeazor GraphRAG knowledge graph.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class EntityType(str, Enum):
    """Types of nodes in the pharmaceutical knowledge graph."""
    DRUG = "DRUG"                               # Commercial product name (e.g. Doliprane, Gelfen)
    ACTIVE_INGREDIENT = "ACTIVE_INGREDIENT"     # Chemical substance / DCI (e.g. Paracétamol, Ibuprofène)
    DOSAGE_FORM = "DOSAGE_FORM"                 # Pharmaceutical form & strength (e.g. 1000 mg comprimé)
    INDICATION = "INDICATION"                   # Disease, symptom or therapeutic use (e.g. Céphalées, Fièvre)
    CONTRAINDICATION = "CONTRAINDICATION"       # Condition prohibiting drug use (e.g. Insuffisance hépatocellulaire)
    ADVERSE_EFFECT = "ADVERSE_EFFECT"           # Known side effect (e.g. Ulcère, Thrombopénie, Prurit)
    INTERACTING_DRUG = "INTERACTING_DRUG"       # Other interacting medication or class (e.g. Anticoagulants oraux)
    POPULATION = "POPULATION"                   # Patient subgroup (e.g. Grossesse, Allaitement, Enfant < 50 kg)
    LABORATORY = "LABORATORY"                   # Pharmaceutical manufacturer (e.g. PROPHARMAL SPA)
    DOSAGE_RULE = "DOSAGE_RULE"                 # Posology constraint (e.g. Max 3 g/jour, Intervalle 4 heures)


class RelationType(str, Enum):
    """Types of edges connecting clinical entities."""
    CONTAINS_ACTIVE_INGREDIENT = "CONTAINS_ACTIVE_INGREDIENT"   # Drug -> DCI
    HAS_DOSAGE_FORM = "HAS_DOSAGE_FORM"                         # Drug -> DosageForm
    TREATS = "TREATS"                                           # DCI/Drug -> Indication
    CONTRAINDICATED_FOR = "CONTRAINDICATED_FOR"                 # DCI/Drug -> Contraindication / Population
    INTERACTS_WITH = "INTERACTS_WITH"                           # DCI/Drug -> InteractingDrug
    HAS_ADVERSE_EFFECT = "HAS_ADVERSE_EFFECT"                   # DCI/Drug -> AdverseEffect
    REQUIRES_PRECAUTION_FOR = "REQUIRES_PRECAUTION_FOR"         # DCI/Drug -> Population / Condition
    HAS_MAX_DOSE = "HAS_MAX_DOSE"                               # Drug -> DosageRule
    MANUFACTURED_BY = "MANUFACTURED_BY"                         # Drug -> Laboratory


@dataclass
class KGEntity:
    """Represents a node in the pharmaceutical knowledge graph."""
    id: str                                     # Unique canonical ID (e.g. 'dci_paracetamol')
    name: str                                   # Human readable name (e.g. 'PARACÉTAMOL')
    entity_type: EntityType                     # Category of entity
    aliases: List[str] = field(default_factory=list) # Synonyms, brand variations
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type.value,
            "aliases": self.aliases,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KGEntity:
        return cls(
            id=data["id"],
            name=data["name"],
            entity_type=EntityType(data["entity_type"]),
            aliases=data.get("aliases", []),
            metadata=data.get("metadata", {}),
        )


@dataclass
class KGRelation:
    """Represents a directed clinical relationship (edge) between two entities."""
    source_id: str                              # Source entity ID
    target_id: str                              # Target entity ID
    relation_type: RelationType                 # Type of relationship
    description: str = ""                       # Contextual clinical explanation
    source_chunk_id: Optional[str] = None       # Provenance chunk ID
    source_doc: Optional[str] = None            # Provenance document (e.g. ANPP RCP)
    confidence: float = 1.0                     # Confidence score [0.0, 1.0]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def edge_key(self) -> str:
        return f"{self.source_id}->{self.relation_type.value}->{self.target_id}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type.value,
            "description": self.description,
            "source_chunk_id": self.source_chunk_id,
            "source_doc": self.source_doc,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KGRelation:
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation_type=RelationType(data["relation_type"]),
            description=data.get("description", ""),
            source_chunk_id=data.get("source_chunk_id"),
            source_doc=data.get("source_doc"),
            confidence=float(data.get("confidence", 1.0)),
            metadata=data.get("metadata", {}),
        )
