"""
Pharmeazor Knowledge Graph - Entity Extractor
=============================================
Extracts canonical clinical entities (DRUG, ACTIVE_INGREDIENT, DOSAGE_FORM,
INDICATION, CONTRAINDICATION, ADVERSE_EFFECT, INTERACTING_DRUG, POPULATION,
LABORATORY, DOSAGE_RULE) from pharmaceutical monographs and text snippets.
"""
# hello 
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Augmentation.knowledge_graph.ontology import EntityType, KGEntity


def normalize_string(s: str) -> str:
    """Normalize string by lowercasing, removing diacritics and non-alphanumeric chars."""
    if not s:
        return ""
    # Remove accents
    nfkd = unicodedata.normalize("NFKD", s)
    no_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    # Replace non-alphanumeric with underscores
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", no_accents.lower()).strip("_")
    return cleaned


def make_entity_id(entity_type: EntityType, name: str) -> str:
    """
    Builds a deterministic, collision-resistant canonical ID.
    Examples:
        'drug_doliprane', 'dci_paracetamol', 'lab_propharmal_spa'
    """
    prefix = entity_type.value.lower()
    norm_name = normalize_string(name)
    if not norm_name:
        norm_name = "unknown"
    # Keep reasonable ID length
    return f"{prefix}_{norm_name[:60]}"


class EntityExtractor:
    """
    Extracts and normalizes pharmaceutical entities from structured documents
    and clinical text sections.
    """

    def __init__(self):
        pass

    def extract_entities_from_document(self, doc: Dict[str, Any]) -> List[KGEntity]:
        """
        Extracts structural entities (Drug, DCI, Laboratory, DosageForm)
        directly from document metadata.
        """
        entities: List[KGEntity] = []
        seen_ids: Set[str] = set()

        # 1. Commercial Brand (DRUG)
        brand = (doc.get("brand") or doc.get("title") or "").strip()
        if brand:
            d_id = make_entity_id(EntityType.DRUG, brand)
            if d_id not in seen_ids:
                seen_ids.add(d_id)
                entities.append(
                    KGEntity(
                        id=d_id,
                        name=brand,
                        entity_type=EntityType.DRUG,
                        aliases=[brand.upper(), brand.lower()],
                        metadata={
                            "drug_id": doc.get("drug_id"),
                            "source": doc.get("source"),
                            "doc_type": doc.get("doc_type"),
                            "dossier": doc.get("dossier", ""),
                        },
                    )
                )

        # 2. Active Substance (ACTIVE_INGREDIENT / DCI)
        dci = (doc.get("dci") or "").strip()
        if dci:
            dci_id = make_entity_id(EntityType.ACTIVE_INGREDIENT, dci)
            if dci_id not in seen_ids:
                seen_ids.add(dci_id)
                entities.append(
                    KGEntity(
                        id=dci_id,
                        name=dci,
                        entity_type=EntityType.ACTIVE_INGREDIENT,
                        aliases=[dci.upper(), dci.lower()],
                        metadata={"drug_id": doc.get("drug_id")},
                    )
                )

        # 3. Laboratory / Manufacturer (LABORATORY)
        lab = (doc.get("lab") or doc.get("manufacturer") or "").strip()
        if lab:
            lab_id = make_entity_id(EntityType.LABORATORY, lab)
            if lab_id not in seen_ids:
                seen_ids.add(lab_id)
                entities.append(
                    KGEntity(
                        id=lab_id,
                        name=lab,
                        entity_type=EntityType.LABORATORY,
                        aliases=[lab.upper(), lab.lower()],
                        metadata={},
                    )
                )

        # 4. Dosage Form (DOSAGE_FORM)
        form = (doc.get("form") or "").strip()
        dosage = (doc.get("dosage") or "").strip()
        cond = (doc.get("conditionnement") or "").strip()
        parts = [p for p in [dosage, form, cond] if p]
        if parts:
            form_name = " ".join(parts).strip()
            df_id = make_entity_id(EntityType.DOSAGE_FORM, form_name)
            if df_id not in seen_ids:
                seen_ids.add(df_id)
                entities.append(
                    KGEntity(
                        id=df_id,
                        name=form_name,
                        entity_type=EntityType.DOSAGE_FORM,
                        aliases=[form_name.upper(), form_name.lower()],
                        metadata={"dosage": dosage, "form": form, "conditionnement": cond},
                    )
                )

        return entities

    def create_entity(
        self,
        name: str,
        entity_type: EntityType,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> KGEntity:
        """Helper to create a single canonical KGEntity."""
        clean_name = name.strip()
        e_id = make_entity_id(entity_type, clean_name)
        return KGEntity(
            id=e_id,
            name=clean_name,
            entity_type=entity_type,
            aliases=[clean_name.upper(), clean_name.lower()],
            metadata=metadata or {},
        )
