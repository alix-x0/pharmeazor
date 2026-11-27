"""
Pharmeazor Knowledge Graph - Entity Extractor
=============================================
Extracts canonical clinical entities from pharmaceutical monographs.

CDC Alignment (Pharmeazor v2 – nov. 2026):
- Entity types now include ATC_CLASS and THERAPEUTIC_CLASS (CDC §1, §4).
- collection_date is propagated from document metadata to every entity (CDC §5).
- source_authority is passed through from document metadata for downstream
  source reconciliation (CDC Fonct. 5).
"""

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

from ai_api.Augmentation.knowledge_graph.ontology import EntityType, KGEntity, SourceAuthority


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

    def resolve_dci(self, doc: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Resolves the active ingredient (DCI) from explicit metadata or falls back
        to section 1.2, active ingredient lists (BDPM/DailyMed), or dossier name.

        Returns:
            (dci_name, was_inferred)
        """
        explicit_dci = (doc.get("dci") or "").strip()
        if explicit_dci:
            return explicit_dci, False

        # Fallback 1: Dedicated DCI section (e.g., key == 'dci' or number == '1.2')
        for sec in doc.get("sections", []):
            raw_key = sec.get("key")
            sec_key = "_".join(raw_key).lower() if isinstance(raw_key, (list, tuple)) else str(raw_key or "").lower()
            sec_num = str(sec.get("number") or "").strip()
            if sec_key == "dci" or sec_num == "1.2":
                candidate = (sec.get("text") or "").strip()
                if 2 <= len(candidate) <= 120 and "sans objet" not in candidate.lower():
                    return candidate, True

        # Fallback 2: Ingredients list (DailyMed active entries or BDPM composition lines)
        active_names: List[str] = []
        for item in doc.get("ingredients", []) or []:
            if not isinstance(item, str):
                continue
            item_str = item.strip()
            if not item_str:
                continue

            # DailyMed format: "ACETAMINOPHEN (ACTIB) - 500 mg" or "... (ACTIVE) ..."
            if "(inactive)" in item_str.lower():
                continue
            if re.search(r"\((?:actib|active)\)", item_str, flags=re.I):
                raw_name = re.split(r"\s*\(", item_str, maxsplit=1)[0].strip()
                norm_name = normalize_string(raw_name)
                mapped = _USAN_TO_DCI.get(norm_name, raw_name)
                if mapped and mapped not in active_names:
                    active_names.append(mapped)
                continue

            # BDPM format: "Paracétamol .......... 1000 mg"
            if not re.match(r"^(?:pour|excipient|liste|voir)\b", item_str, flags=re.I):
                cleaned = re.split(r"\.{3,}|\s+\d+[\.,]?\d*\s*(?:mg|g|ml|mcg|µg|%)\b", item_str, maxsplit=1, flags=re.I)[0]
                cleaned = re.sub(r"\s+", " ", cleaned).strip(" .:-")
                if 3 <= len(cleaned) <= 80:
                    norm_name = normalize_string(cleaned)
                    mapped = _USAN_TO_DCI.get(norm_name, cleaned)
                    if mapped and mapped not in active_names:
                        active_names.append(mapped)

        if active_names:
            return " / ".join(active_names[:3]), True

        # Fallback 3: Curated dossier folder name
        dossier = (doc.get("dossier") or "").strip()
        if dossier:
            if dossier in DOSSIER_DCI_MAP:
                return DOSSIER_DCI_MAP[dossier], True
            slug = re.sub(r"^\d+_", "", dossier).replace("-", " ").strip().upper()
            if slug:
                return slug, True

        return "", False

    def extract_entities_from_document(self, doc: Dict[str, Any]) -> List[KGEntity]:
        """
        Extracts structural entities (Drug, DCI, Laboratory, DosageForm, ATC_CLASS,
        THERAPEUTIC_CLASS) directly from document metadata.

        CDC §5: collection_date is read from doc metadata and stamped on every entity.
        CDC §4: ATC code and therapeutic class are extracted as first-class entities.
        """
        entities: List[KGEntity] = []
        seen_ids: Set[str] = set()

        # CDC §5 — date of collection must be tracked on every entity
        collection_date: Optional[str] = doc.get("collection_date") or doc.get("date_collecte")

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
                        collection_date=collection_date,
                        metadata={
                            "drug_id": doc.get("drug_id"),
                            "source": doc.get("source"),
                            "doc_type": doc.get("doc_type"),
                            "dossier": doc.get("dossier", ""),
                            # Princeps/générique flag for IS_EQUIVALENT_TO linking (CDC §3 Inclus)
                            "is_princeps": doc.get("is_princeps"),
                        },
                    )
                )

        # 2. Active Substance (ACTIVE_INGREDIENT / DCI)
        dci, dci_inferred = self.resolve_dci(doc)
        if dci:
            dci_id = make_entity_id(EntityType.ACTIVE_INGREDIENT, dci)
            if dci_id not in seen_ids:
                seen_ids.add(dci_id)
                dci_meta: Dict[str, Any] = {"drug_id": doc.get("drug_id")}
                if dci_inferred:
                    dci_meta["dci_inferred"] = True
                entities.append(
                    KGEntity(
                        id=dci_id,
                        name=dci,
                        entity_type=EntityType.ACTIVE_INGREDIENT,
                        aliases=[dci.upper(), dci.lower()],
                        collection_date=collection_date,
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
                        collection_date=collection_date,
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
                        collection_date=collection_date,
                        metadata={"dosage": dosage, "form": form, "conditionnement": cond},
                    )
                )

        # 5. ATC Class (CDC §1 vocabulary table: "Code ATC")
        atc_code = (doc.get("atc_code") or doc.get("code_atc") or "").strip().upper()
        if atc_code:
            atc_id = make_entity_id(EntityType.ATC_CLASS, atc_code)
            if atc_id not in seen_ids:
                seen_ids.add(atc_id)
                entities.append(
                    KGEntity(
                        id=atc_id,
                        name=atc_code,
                        entity_type=EntityType.ATC_CLASS,
                        aliases=[],
                        collection_date=collection_date,
                        metadata={"atc_code": atc_code},
                    )
                )

        # 6. Therapeutic Class (CDC §4: antalgiques, antibiotiques, antihypertenseurs)
        therapeutic_class = (
            doc.get("therapeutic_class")
            or doc.get("classe_therapeutique")
            or ""
        ).strip()
        if therapeutic_class:
            tc_id = make_entity_id(EntityType.THERAPEUTIC_CLASS, therapeutic_class)
            if tc_id not in seen_ids:
                seen_ids.add(tc_id)
                entities.append(
                    KGEntity(
                        id=tc_id,
                        name=therapeutic_class,
                        entity_type=EntityType.THERAPEUTIC_CLASS,
                        aliases=[therapeutic_class.lower(), therapeutic_class.upper()],
                        collection_date=collection_date,
                        metadata={},
                    )
                )

        return entities

    def create_entity(
        self,
        name: str,
        entity_type: EntityType,
        metadata: Optional[Dict[str, Any]] = None,
        collection_date: Optional[str] = None,
    ) -> KGEntity:
        """
        Helper to create a single canonical KGEntity.
        collection_date should always be supplied to satisfy CDC §5.
        """
        clean_name = name.strip()
        e_id = make_entity_id(entity_type, clean_name)
        return KGEntity(
            id=e_id,
            name=clean_name,
            entity_type=entity_type,
            aliases=[clean_name.upper(), clean_name.lower()],
            collection_date=collection_date,
            metadata=metadata or {},
        )
