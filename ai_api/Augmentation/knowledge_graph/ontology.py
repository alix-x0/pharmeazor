"""
Pharmeazor Knowledge Graph - Pharmaceutical Ontology & Schema
==============================================================
Defines canonical clinical entity types, relationship types, and data models
for the Pharmeazor GraphRAG knowledge graph.

CDC Alignment (Pharmeazor v2 – nov. 2026):
- Entities cover all required "Inclus" items: identification, indications,
  contre-indications, posologie, interactions, effets indésirables, équivalents.
- Source authority levels follow the CDC §3 trust hierarchy (ANPP RCP > … > non-officiel).
- Interaction severity levels match the ANSM Thésaurus 4-level classification (CDC §2).
- Provenance fields (source_authority, collection_date) support source reconciliation (CDC Fonct. 5).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum, IntEnum
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Authority & Severity Enumerations (CDC-mandated)
# ---------------------------------------------------------------------------

class SourceAuthority(IntEnum):
    """
    Source trust hierarchy as defined in CDC §3 ("Toutes les sources n'ont pas le même poids").
    Lower integer = higher authority. Used for source reconciliation (CDC Fonct. 5).
    """
    ANPP_RCP              = 1  # RCP/notice validée par l'ANPP (Algérie) — source prioritaire
    NOMENCLATURE_OFFICIELLE = 2  # Nomenclature officielle du ministère algérien
    INSTITUTIONNEL_ETRANGER = 3  # ANSM Thésaurus, DailyMed (FDA), EMA — complément uniquement
    PROFESSIONNEL_ALGERIEN  = 4  # Pharm'Net, MEDAlgérie, dzair-pharma — source secondaire
    NON_OFFICIEL            = 5  # Forums, blogs — à écarter (jamais utilisé en production)


class InteractionSeverity(str, Enum):
    """
    Four-level ANSM interaction severity classification (CDC §2).
    Must always be displayed alongside any interaction alert.
    """
    CONTRE_INDICATION     = "CONTRE_INDICATION"      # Association ne doit pas être faite
    DECONSEILLEE          = "DECONSEILLEE"            # À éviter, sauf nécessité
    PRECAUTION_D_EMPLOI   = "PRECAUTION_D_EMPLOI"    # Possible, avec surveillance ou ajustement
    A_PRENDRE_EN_COMPTE   = "A_PRENDRE_EN_COMPTE"    # Risque à garder en tête


# ---------------------------------------------------------------------------
# Entity Types
# ---------------------------------------------------------------------------

class EntityType(str, Enum):
    """Types of nodes in the pharmaceutical knowledge graph."""
    DRUG                = "DRUG"                # Commercial product name (e.g. Doliprane, Gelfen)
    ACTIVE_INGREDIENT   = "ACTIVE_INGREDIENT"   # Chemical substance / DCI (e.g. Paracétamol, Ibuprofène)
    DOSAGE_FORM         = "DOSAGE_FORM"         # Pharmaceutical form & strength (e.g. 1000 mg comprimé)
    INDICATION          = "INDICATION"          # Disease/symptom (e.g. Céphalées, Fièvre, Hypertension)
    CONTRAINDICATION    = "CONTRAINDICATION"    # Condition prohibiting use (e.g. Insuffisance hépatocellulaire)
    ADVERSE_EFFECT      = "ADVERSE_EFFECT"      # Known side effect (e.g. Ulcère, Thrombopénie, Prurit)
    INTERACTING_DRUG    = "INTERACTING_DRUG"    # Interacting medication or class (e.g. Anticoagulants oraux)
    POPULATION          = "POPULATION"          # Patient subgroup (e.g. Grossesse, Allaitement, Enfant < 50 kg)
    LABORATORY          = "LABORATORY"          # Pharmaceutical manufacturer (e.g. PROPHARMAL SPA)
    DOSAGE_RULE         = "DOSAGE_RULE"         # Posology constraint (e.g. Max 3 g/jour, Intervalle 4 h)
    # --- Added to satisfy CDC requirements ---
    ATC_CLASS           = "ATC_CLASS"           # ATC classification node (e.g. N02BE01 – Paracétamol)
    THERAPEUTIC_CLASS   = "THERAPEUTIC_CLASS"   # One of the 3 CDC project classes (antalgiques, antibiotiques, antihypertenseurs)


# ---------------------------------------------------------------------------
# Relation Types
# ---------------------------------------------------------------------------

class RelationType(str, Enum):
    """Types of directed edges connecting clinical entities."""
    # Structural / identity
    CONTAINS_ACTIVE_INGREDIENT = "CONTAINS_ACTIVE_INGREDIENT"   # Drug -> DCI
    HAS_DOSAGE_FORM            = "HAS_DOSAGE_FORM"              # Drug -> DosageForm
    MANUFACTURED_BY            = "MANUFACTURED_BY"              # Drug -> Laboratory
    HAS_ATC_CODE               = "HAS_ATC_CODE"                 # Drug/DCI -> ATC_CLASS
    BELONGS_TO_CLASS           = "BELONGS_TO_CLASS"             # Drug/DCI -> THERAPEUTIC_CLASS
    IS_EQUIVALENT_TO           = "IS_EQUIVALENT_TO"             # Drug <-> Drug (princeps/générique, même DCI+forme+dosage)
    # Clinical safety
    TREATS                     = "TREATS"                       # DCI/Drug -> Indication
    CONTRAINDICATED_FOR        = "CONTRAINDICATED_FOR"          # DCI/Drug -> Contraindication / Population
    INTERACTS_WITH             = "INTERACTS_WITH"               # DCI/Drug -> InteractingDrug (carry severity)
    HAS_ADVERSE_EFFECT         = "HAS_ADVERSE_EFFECT"           # DCI/Drug -> AdverseEffect
    REQUIRES_PRECAUTION_FOR    = "REQUIRES_PRECAUTION_FOR"      # DCI/Drug -> Population / Condition
    # Posology (split to avoid semantic mismatch)
    HAS_MAX_DOSE               = "HAS_MAX_DOSE"                 # Drug -> DosageRule  [explicit max dose only]
    HAS_POSOLOGY               = "HAS_POSOLOGY"                 # Drug -> DosageRule  [interval, freq, population adaptation]


@dataclass
class KGEntity:
    """
    Represents a node in the pharmaceutical knowledge graph.
    Every entity must carry its collection_date for versioning (CDC §5).
    """
    id: str                                          # Unique canonical ID (e.g. 'dci_paracetamol')
    name: str                                        # Human-readable name (e.g. 'PARACÉTAMOL')
    entity_type: EntityType                          # Category of entity
    aliases: List[str] = field(default_factory=list) # Synonyms, brand variations, ATC variants
    collection_date: Optional[str] = None            # ISO date of data collection — required by CDC §5
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type.value,
            "aliases": self.aliases,
            "collection_date": self.collection_date,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KGEntity:
        return cls(
            id=data["id"],
            name=data["name"],
            entity_type=EntityType(data["entity_type"]),
            aliases=data.get("aliases", []),
            collection_date=data.get("collection_date"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class KGRelation:
    """
    Represents a directed clinical relationship (edge) between two entities.

    Key CDC requirements reflected here:
    - severity: mandatory for INTERACTS_WITH edges (ANSM 4-level scale, CDC §2)
    - source_authority: enables source reconciliation — higher authority wins (CDC Fonct. 5)
    - collection_date: every piece of information must carry its collection date (CDC §5)
    - source_chunk_id / source_doc: verbatim provenance for every clinical claim (CDC Fonct. 2 & 4)
    """
    source_id: str                                        # Source entity ID
    target_id: str                                        # Target entity ID
    relation_type: RelationType                           # Type of relationship
    description: str = ""                                 # Contextual/verbatim clinical explanation
    source_chunk_id: Optional[str] = None                 # Provenance chunk ID
    source_doc: Optional[str] = None                      # Provenance document (e.g. ANPP RCP)
    source_authority: Optional[SourceAuthority] = None    # Trust level of the source (CDC §3)
    collection_date: Optional[str] = None                 # ISO date when this data was collected (CDC §5)
    severity: Optional[InteractionSeverity] = None        # For INTERACTS_WITH: ANSM 4-level severity (CDC §2)
    confidence: float = 1.0                               # Confidence score [0.0, 1.0]
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
            "source_authority": self.source_authority.value if self.source_authority is not None else None,
            "collection_date": self.collection_date,
            "severity": self.severity.value if self.severity is not None else None,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KGRelation:
        raw_auth = data.get("source_authority")
        raw_sev = data.get("severity")
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation_type=RelationType(data["relation_type"]),
            description=data.get("description", ""),
            source_chunk_id=data.get("source_chunk_id"),
            source_doc=data.get("source_doc"),
            source_authority=SourceAuthority(raw_auth) if raw_auth is not None else None,
            collection_date=data.get("collection_date"),
            severity=InteractionSeverity(raw_sev) if raw_sev is not None else None,
            confidence=float(data.get("confidence", 1.0)),
            metadata=data.get("metadata", {}),
        )
