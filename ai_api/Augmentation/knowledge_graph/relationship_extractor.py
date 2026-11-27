"""
Pharmeazor Knowledge Graph - Relationship Extractor
===================================================
Extracts high-precision clinical and structural relationships connecting
pharmaceutical entities from official monographs (ANPP, BDPM, DailyMed, Pharmnet).

CRITICAL MEDICAL SAFETY & GROUNDING POLICY:
-------------------------------------------
- Zero Unsupported Medical Inference: The system never deduces, invents, or generalizes
  clinical rules, indications, interactions, or contraindications not explicitly stated
  in the monograph text.
- Verbatim Provenance: Every clinical relationship MUST be backed by an exact,
  unmodified verbatim quote ('evidence_text') from the official document.
- Audit Verification: Every extracted relation is verified against the source text
  via the Provenance engine. Any relation lacking verbatim textual proof is rejected.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, Tuple, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Augmentation.knowledge_graph.entity_extractor import (
    EntityExtractor,
    make_entity_id,
    normalize_string,
)
from ai_api.Augmentation.knowledge_graph.entity_normalizer import (
    EntityNormalizer,
    default_normalizer,
)
from ai_api.Augmentation.knowledge_graph.ontology import (
    EntityType,
    KGEntity,
    KGRelation,
    RelationType,
)
from ai_api.Augmentation.knowledge_graph.provenance import (
    ProvenanceRecord,
    validate_relation_grounding,
)

logger = logging.getLogger(__name__)

# Default location of curated corpus
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "outputs_data"

# Common boilerplate phrases and regulatory notices to ignore
IGNORE_SUBSTRINGS = {
    "sans objet",
    "non applicable",
    "section vide",
    "redirection vers le haut de page",
    "voir rubrique",
    "aucune etude",
    "aucun effet",
    "declaration des effets indesirables",
    "centre national de pharmacovigilance",
    "classe pharmacotherapeutique",
    "code atc",
}

# MedDRA system organ class headers to ignore in adverse effects
MEDDRA_CLASS_PREFIXES = (
    "affections ",
    "troubles ",
    "classe de systemes",
    "soc ",
    "infections et infestations",
    "tumeurs ",
    "investigations",
)


@dataclass
class ExtractionResult:
    """Container holding entities and relationships extracted from data."""
    relations: List[KGRelation] = field(default_factory=list)
    entities: List[KGEntity] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities_count": len(self.entities),
            "relations_count": len(self.relations),
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
        }


class RelationshipExtractor:
    """
    Extracts, normalizes, and strictly grounds clinical and pharmacological
    relationships from structured drug monographs with zero speculative inference.
    """

    def __init__(
        self,
        confidence_threshold: float = 0.7,
        normalizer: Optional[EntityNormalizer] = None,
    ):
        self.confidence_threshold = confidence_threshold
        self.entity_extractor = EntityExtractor()
        self.normalizer = normalizer or default_normalizer

    # --------------------------------------------------------------------------
    # Text Cleaning & Clinical Filtering
    # --------------------------------------------------------------------------

    def clean_item_text(self, text: str) -> str:
        """Cleans bullet points, trailing references, and extra whitespace."""
        if not text:
            return ""
        # Remove leading bullet symbols, numbers, punctuation
        t = re.sub(r"^[\s•\-\*\+\d\.\)\:]+", "", text).strip()
        # Remove trailing regulatory section references: (voir rubrique 4.4) or (voir 6.1)
        t = re.sub(r"\(voir\s+rubrique[^\)]*\)", "", t, flags=re.I).strip()
        t = re.sub(r"\(voir[^\)]*\)", "", t, flags=re.I).strip()
        # Normalize whitespace
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def is_valid_clinical_item(self, text: str) -> bool:
        """Filters out headers, empty lines, and regulatory boilerplate."""
        if not text or len(text) < 3 or len(text) > 350:
            return False
        norm = self.normalizer.clean_text(text)
        for ign in IGNORE_SUBSTRINGS:
            if ign in norm:
                return False
        return True

    @staticmethod
    def split_smart_commas(text: str) -> List[str]:
        """
        Splits by comma only when outside parentheses to preserve complex clinical terms
        like 'hépatite (ictère, élévation des transaminases)'.
        """
        parts = re.split(r",(?![^(]*\))", text)
        return [p.strip() for p in parts if p.strip()]

    # --------------------------------------------------------------------------
    # Document Level Extraction (Strict Grounding Enforcement)
    # --------------------------------------------------------------------------

    def extract_from_document(
        self,
        doc: Dict[str, Any],
        doc_id: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extracts all entities and relationships from a single monograph document.
        Strictly enforces that every clinical relation has verbatim evidence in the text.
        """
        raw_entities: Dict[str, KGEntity] = {}
        candidate_relations: List[KGRelation] = []
        seen_edges: Set[str] = set()

        doc_name = (doc.get("brand") or doc.get("title") or "Unknown").strip()
        doc_file = doc_id or f"{doc_name}.json"

        # 1. Structural Entities & Direct Grounded Relationships
        base_entities = self.entity_extractor.extract_entities_from_document(doc)
        normalized_base: List[KGEntity] = []
        for e in base_entities:
            norm_e = self.normalizer.normalize_entity(e)
            raw_entities[norm_e.id] = norm_e
            normalized_base.append(norm_e)

        drug_entity = next((e for e in normalized_base if e.entity_type == EntityType.DRUG), None)
        dci_entity = next((e for e in normalized_base if e.entity_type == EntityType.ACTIVE_INGREDIENT), None)
        lab_entity = next((e for e in normalized_base if e.entity_type == EntityType.LABORATORY), None)
        form_entity = next((e for e in normalized_base if e.entity_type == EntityType.DOSAGE_FORM), None)

        primary_id = drug_entity.id if drug_entity else (dci_entity.id if dci_entity else None)
        if not primary_id:
            return ExtractionResult()

        # Drug -> CONTAINS_ACTIVE_INGREDIENT -> DCI
        if drug_entity and dci_entity:
            rel = KGRelation(
                source_id=drug_entity.id,
                target_id=dci_entity.id,
                relation_type=RelationType.CONTAINS_ACTIVE_INGREDIENT,
                description=f"{drug_entity.name} contient la substance active {dci_entity.name}",
                source_doc=doc_file,
                confidence=1.0,
                metadata={"grounded_in": "metadata.dci"},
            )
            if rel.edge_key not in seen_edges:
                seen_edges.add(rel.edge_key)
                candidate_relations.append(rel)

        # Drug -> MANUFACTURED_BY -> Laboratory
        if drug_entity and lab_entity:
            rel = KGRelation(
                source_id=drug_entity.id,
                target_id=lab_entity.id,
                relation_type=RelationType.MANUFACTURED_BY,
                description=f"{drug_entity.name} est fabriqué/exploité par {lab_entity.name}",
                source_doc=doc_file,
                confidence=1.0,
                metadata={"grounded_in": "metadata.lab"},
            )
            if rel.edge_key not in seen_edges:
                seen_edges.add(rel.edge_key)
                candidate_relations.append(rel)

        # Drug -> HAS_DOSAGE_FORM -> DosageForm
        if drug_entity and form_entity:
            rel = KGRelation(
                source_id=drug_entity.id,
                target_id=form_entity.id,
                relation_type=RelationType.HAS_DOSAGE_FORM,
                description=f"{drug_entity.name} se présente sous la forme {form_entity.name}",
                source_doc=doc_file,
                confidence=1.0,
                metadata={"grounded_in": "metadata.dosage_form"},
            )
            if rel.edge_key not in seen_edges:
                seen_edges.add(rel.edge_key)
                candidate_relations.append(rel)

        # 2. Extract Clinical Relationships Strictly from Document Sections
        sections = doc.get("sections", [])
        for sec in sections:
            raw_key = sec.get("key")
            sec_key = "_".join(raw_key).lower() if isinstance(raw_key, (list, tuple)) else str(raw_key or "").lower()
            sec_text = (sec.get("text") or "").strip()
            sec_num = str(sec.get("number", ""))
            sec_title = str(sec.get("title", ""))
            if not sec_text:
                continue

            sec_context = {
                "doc_file": doc_file,
                "section_key": sec_key,
                "section_number": sec_num,
                "section_title": sec_title,
            }

            # 4.1 Indications thérapeutiques
            if "indication" in sec_key or sec_num == "4.1":
                self._extract_indications(
                    sec_text, primary_id, dci_entity, sec_context, raw_entities, candidate_relations, seen_edges
                )

            # 4.2 Posologie et mode d'administration
            elif "posolog" in sec_key or sec_num == "4.2":
                self._extract_posology_rules(
                    sec_text, primary_id, sec_context, raw_entities, candidate_relations, seen_edges
                )

            # 4.3 Contre-indications
            elif "contre_indication" in sec_key or "contraindication" in sec_key or sec_num == "4.3":
                self._extract_contraindications(
                    sec_text, primary_id, dci_entity, sec_context, raw_entities, candidate_relations, seen_edges
                )

            # 4.4 Mises en garde et précautions d'emploi
            elif "mise_en_garde" in sec_key or "precaution" in sec_key or sec_num == "4.4":
                self._extract_precautions(
                    sec_text, primary_id, dci_entity, sec_context, raw_entities, candidate_relations, seen_edges
                )

            # 4.5 Interactions médicamenteuses
            elif "interaction" in sec_key or sec_num == "4.5":
                self._extract_interactions(
                    sec_text, primary_id, dci_entity, sec_context, raw_entities, candidate_relations, seen_edges
                )

            # 4.6 Fertilité, grossesse et allaitement
            elif "fertilite" in sec_key or "grossesse" in sec_key or "pregnancy" in sec_key or sec_num == "4.6":
                self._extract_pregnancy_relations(
                    sec_text, primary_id, dci_entity, sec_context, raw_entities, candidate_relations, seen_edges
                )

            # 4.8 Effets indésirables
            elif "effet" in sec_key or "adverse" in sec_key or sec_num == "4.8":
                self._extract_adverse_effects(
                    sec_text, primary_id, dci_entity, sec_context, raw_entities, candidate_relations, seen_edges
                )

        # 3. CRITICAL AUDIT: Validate grounding for every relation against the document text
        verified_relations: List[KGRelation] = []
        for rel in candidate_relations:
            if validate_relation_grounding(rel, doc):
                verified_relations.append(rel)
            else:
                logger.warning("Dropped ungrounded relation: %s", rel.edge_key)

        # 4. Canonicalize & Deduplicate accumulated entities
        final_entities = self.normalizer.deduplicate_entities(raw_entities.values())

        return ExtractionResult(relations=verified_relations, entities=final_entities)

    # --------------------------------------------------------------------------
    # Helper to create & normalize canonical KGEntity
    # --------------------------------------------------------------------------

    def _register_clinical_entity(
        self,
        name: str,
        entity_type: EntityType,
        entities: Dict[str, KGEntity],
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Resolves canonical name and ID, creates/normalizes KGEntity,
        and adds it to the entities dictionary if not present. Returns the canonical entity ID.
        """
        canon_name = self.normalizer.resolve_canonical_name(name, entity_type)
        ent_id = make_entity_id(entity_type, canon_name)

        if ent_id not in entities:
            meta = extra_metadata or {}
            meta["raw_name"] = name
            raw_ent = self.entity_extractor.create_entity(canon_name, entity_type, metadata=meta)
            norm_ent = self.normalizer.normalize_entity(raw_ent)
            entities[ent_id] = norm_ent

        return ent_id

    # --------------------------------------------------------------------------
    # Specific Clinical Section Handlers (Strict Verbatim Grounding)
    # --------------------------------------------------------------------------

    def _extract_indications(
        self,
        text: str,
        primary_id: str,
        dci_entity: Optional[KGEntity],
        sec_context: Dict[str, str],
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts TREATS relationships strictly grounded in section 4.1 text."""
        candidates = re.split(r"[\n•\-\*\;\.]+", text)
        for cand in candidates:
            item = self.clean_item_text(cand)
            if not self.is_valid_clinical_item(item):
                continue

            # Must contain explicit therapeutic indication keywords
            if any(w in item.lower() for w in [
                "traitement", "indique", "douleur", "fievre", "arthrose", "migraine",
                "infection", "hypertension", "angine", "rhin", "otite", "toux", "inflamm",
                "symptomatique", "etats febriles", "cephalee"
            ]):
                # Verbatim quote is the exact candidate line from the document
                verbatim_evidence = cand.strip()
                ent_id = self._register_clinical_entity(item, EntityType.INDICATION, entities)

                rel_meta = {
                    "evidence_text": verbatim_evidence,
                    "section_key": sec_context["section_key"],
                    "section_number": sec_context["section_number"],
                    "section_title": sec_context["section_title"],
                }

                rel = KGRelation(
                    source_id=primary_id,
                    target_id=ent_id,
                    relation_type=RelationType.TREATS,
                    description=verbatim_evidence,
                    source_doc=sec_context["doc_file"],
                    confidence=1.0,
                    metadata=rel_meta,
                )
                if rel.edge_key not in seen_edges:
                    seen_edges.add(rel.edge_key)
                    relations.append(rel)

                if dci_entity and dci_entity.id != primary_id:
                    rel_dci = KGRelation(
                        source_id=dci_entity.id,
                        target_id=ent_id,
                        relation_type=RelationType.TREATS,
                        description=verbatim_evidence,
                        source_doc=sec_context["doc_file"],
                        confidence=1.0,
                        metadata=rel_meta,
                    )
                    if rel_dci.edge_key not in seen_edges:
                        seen_edges.add(rel_dci.edge_key)
                        relations.append(rel_dci)

    def _extract_posology_rules(
        self,
        text: str,
        primary_id: str,
        sec_context: Dict[str, str],
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """
        Extracts HAS_MAX_DOSE and posology rules strictly grounded in verbatim text.
        Never fabricates synthetic rule descriptions.
        """
        sentences = [s.strip() for s in re.split(r"[\n\.]+", text) if len(s.strip()) >= 5]

        for sentence in sentences:
            s_low = sentence.lower()

            # 1. Maximum daily dose statement
            if any(p in s_low for p in ["dose maximale", "posologie maximale", "ne pas depasser", "dose journaliere maximale"]):
                dose_matches = re.findall(r"(\d+[\s\.,]?\d*\s*(?:mg|g)\b)", sentence, flags=re.I)
                if dose_matches:
                    dose_mg = self.normalizer.parse_dosage_value_mg(sentence)
                    rule_name = self.clean_item_text(sentence)
                    ent_id = self._register_clinical_entity(
                        rule_name,
                        EntityType.DOSAGE_RULE,
                        entities,
                        extra_metadata={"dose_mg": dose_mg, "rule_type": "max_daily_dose"},
                    )
                    rel = KGRelation(
                        source_id=primary_id,
                        target_id=ent_id,
                        relation_type=RelationType.HAS_MAX_DOSE,
                        description=sentence,  # Verbatim sentence from document
                        source_doc=sec_context["doc_file"],
                        confidence=1.0,
                        metadata={
                            "evidence_text": sentence,
                            "rule_type": "max_daily_dose",
                            "dose_mg": dose_mg,
                            "section_key": sec_context["section_key"],
                            "section_number": sec_context["section_number"],
                        },
                    )
                    if rel.edge_key not in seen_edges:
                        seen_edges.add(rel.edge_key)
                        relations.append(rel)

            # 2. Intake interval constraints
            if "intervalle" in s_low or "entre chaque prise" in s_low or "entre deux prises" in s_low:
                if re.search(r"\b\d+\s*heures?\b", sentence, flags=re.I):
                    rule_name = self.clean_item_text(sentence)
                    ent_id = self._register_clinical_entity(
                        rule_name,
                        EntityType.DOSAGE_RULE,
                        entities,
                        extra_metadata={"rule_type": "interval"},
                    )
                    rel = KGRelation(
                        source_id=primary_id,
                        target_id=ent_id,
                        relation_type=RelationType.HAS_MAX_DOSE,
                        description=sentence,  # Verbatim
                        source_doc=sec_context["doc_file"],
                        confidence=1.0,
                        metadata={
                            "evidence_text": sentence,
                            "rule_type": "interval",
                            "section_key": sec_context["section_key"],
                            "section_number": sec_context["section_number"],
                        },
                    )
                    if rel.edge_key not in seen_edges:
                        seen_edges.add(rel.edge_key)
                        relations.append(rel)

            # 3. Patient weight & special population constraints
            if any(term in s_low for term in ["pesant", "poids", "kg", "insuffisance renale", "insuffisance hepatique"]):
                if any(kw in s_low for kw in ["dose", "posologie", "adapter", "uniquement sur avis", "contre-indiqu"]):
                    rule_name = self.clean_item_text(sentence)
                    if self.is_valid_clinical_item(rule_name):
                        ent_id = self._register_clinical_entity(
                            rule_name,
                            EntityType.DOSAGE_RULE,
                            entities,
                            extra_metadata={"rule_type": "population_adaptation"},
                        )
                        rel = KGRelation(
                            source_id=primary_id,
                            target_id=ent_id,
                            relation_type=RelationType.HAS_MAX_DOSE,
                            description=sentence,  # Verbatim
                            source_doc=sec_context["doc_file"],
                            confidence=1.0,
                            metadata={
                                "evidence_text": sentence,
                                "rule_type": "population_adaptation",
                                "section_key": sec_context["section_key"],
                                "section_number": sec_context["section_number"],
                            },
                        )
                        if rel.edge_key not in seen_edges:
                            seen_edges.add(rel.edge_key)
                            relations.append(rel)

    def _extract_contraindications(
        self,
        text: str,
        primary_id: str,
        dci_entity: Optional[KGEntity],
        sec_context: Dict[str, str],
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts CONTRAINDICATED_FOR relationships grounded in Section 4.3 verbatim text."""
        lines = re.split(r"[\n•\-\*]+", text)
        for line in lines:
            item = self.clean_item_text(line)
            if not self.is_valid_clinical_item(item):
                continue

            ent_id = self._register_clinical_entity(item, EntityType.CONTRAINDICATION, entities)
            rel_meta = {
                "evidence_text": line.strip(),
                "section_key": sec_context["section_key"],
                "section_number": sec_context["section_number"],
                "section_title": sec_context["section_title"],
            }

            rel = KGRelation(
                source_id=primary_id,
                target_id=ent_id,
                relation_type=RelationType.CONTRAINDICATED_FOR,
                description=line.strip(),
                source_doc=sec_context["doc_file"],
                confidence=1.0,
                metadata=rel_meta,
            )
            if rel.edge_key not in seen_edges:
                seen_edges.add(rel.edge_key)
                relations.append(rel)

            if dci_entity and dci_entity.id != primary_id:
                rel_dci = KGRelation(
                    source_id=dci_entity.id,
                    target_id=ent_id,
                    relation_type=RelationType.CONTRAINDICATED_FOR,
                    description=line.strip(),
                    source_doc=sec_context["doc_file"],
                    confidence=1.0,
                    metadata=rel_meta,
                )
                if rel_dci.edge_key not in seen_edges:
                    seen_edges.add(rel_dci.edge_key)
                    relations.append(rel_dci)

    def _extract_precautions(
        self,
        text: str,
        primary_id: str,
        dci_entity: Optional[KGEntity],
        sec_context: Dict[str, str],
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts REQUIRES_PRECAUTION_FOR relationships grounded in Section 4.4 text."""
        lines = re.split(r"[\n•\-\*]+", text)
        for line in lines:
            item = self.clean_item_text(line)
            if not self.is_valid_clinical_item(item):
                continue

            # Clinical risk and precaution keywords
            if any(w in item.lower() for w in [
                "insuffisance", "poids", "enfant", "alcool", "g6pd", "deshydratation",
                "malnutrition", "sujet age", "personne agee", "syndrome", "risque", "precaution"
            ]):
                ent_id = self._register_clinical_entity(item, EntityType.POPULATION, entities)
                rel_meta = {
                    "evidence_text": line.strip(),
                    "section_key": sec_context["section_key"],
                    "section_number": sec_context["section_number"],
                }

                rel = KGRelation(
                    source_id=primary_id,
                    target_id=ent_id,
                    relation_type=RelationType.REQUIRES_PRECAUTION_FOR,
                    description=line.strip(),
                    source_doc=sec_context["doc_file"],
                    confidence=1.0,
                    metadata=rel_meta,
                )
                if rel.edge_key not in seen_edges:
                    seen_edges.add(rel.edge_key)
                    relations.append(rel)

    def _extract_interactions(
        self,
        text: str,
        primary_id: str,
        dci_entity: Optional[KGEntity],
        sec_context: Dict[str, str],
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts INTERACTS_WITH relationships grounded in Section 4.5 verbatim text."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        current_drug: Optional[str] = None
        current_desc: List[str] = []
        current_severity: str = "A_PRENDRE_EN_COMPTE"

        def flush_interaction():
            nonlocal current_drug, current_desc, current_severity
            if current_drug:
                cleaned_name = self.clean_item_text(current_drug)
                if self.is_valid_clinical_item(cleaned_name):
                    full_verbatim = current_drug + (" : " + " ".join(current_desc) if current_desc else "")
                    meta = {
                        "severity": current_severity,
                        "evidence_text": current_drug,
                        "section_key": sec_context["section_key"],
                        "section_number": sec_context["section_number"],
                    }
                    ent_id = self._register_clinical_entity(
                        cleaned_name, EntityType.INTERACTING_DRUG, entities, extra_metadata=meta
                    )

                    rel = KGRelation(
                        source_id=primary_id,
                        target_id=ent_id,
                        relation_type=RelationType.INTERACTS_WITH,
                        description=full_verbatim,
                        source_doc=sec_context["doc_file"],
                        confidence=1.0,
                        metadata=meta,
                    )
                    if rel.edge_key not in seen_edges:
                        seen_edges.add(rel.edge_key)
                        relations.append(rel)

                    if dci_entity and dci_entity.id != primary_id:
                        rel_dci = KGRelation(
                            source_id=dci_entity.id,
                            target_id=ent_id,
                            relation_type=RelationType.INTERACTS_WITH,
                            description=full_verbatim,
                            source_doc=sec_context["doc_file"],
                            confidence=1.0,
                            metadata=meta,
                        )
                        if rel_dci.edge_key not in seen_edges:
                            seen_edges.add(rel_dci.edge_key)
                            relations.append(rel_dci)
            current_drug = None
            current_desc = []

        for line in lines:
            line_low = line.lower()
            if "contre-indiqu" in line_low:
                current_severity = "CONTRAINDICATION"
            elif "deconseill" in line_low:
                current_severity = "DECONSEILLEE"
            elif "precaution" in line_low:
                current_severity = "PRECAUTION_D_EMPLOI"

            # Bulleted interacting drug entry
            if re.match(r"^[\+\•\-]\s+[A-ZÀ-ÿ]", line):
                flush_interaction()
                current_drug = line
            elif current_drug:
                current_desc.append(line)
        flush_interaction()

    def _extract_pregnancy_relations(
        self,
        text: str,
        primary_id: str,
        dci_entity: Optional[KGEntity],
        sec_context: Dict[str, str],
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """
        Extracts pregnancy and lactation relations ONLY when an explicit clinical statement
        is made in a specific sentence. Never deduces safety from mere word presence.
        """
        sentences = [s.strip() for s in re.split(r"[\n\.]+", text) if len(s.strip()) >= 10]

        for sentence in sentences:
            s_low = sentence.lower()

            # Pregnancy statement with explicit directive
            if "grossesse" in s_low or "enceinte" in s_low:
                has_contraindication = any(w in s_low for w in ["contre-indiqu", "ne doit pas etre utilise", "deconseill", "eviter"])
                has_precaution = any(w in s_low for w in ["prudence", "avec precaution", "sur avis medical", "en cas de besoin"])

                if has_contraindication or has_precaution:
                    pop_name = "Grossesse"
                    ent_id = self._register_clinical_entity(pop_name, EntityType.POPULATION, entities)
                    rel_type = RelationType.CONTRAINDICATED_FOR if has_contraindication else RelationType.REQUIRES_PRECAUTION_FOR

                    rel = KGRelation(
                        source_id=primary_id,
                        target_id=ent_id,
                        relation_type=rel_type,
                        description=sentence,  # Verbatim sentence from document
                        source_doc=sec_context["doc_file"],
                        confidence=1.0,
                        metadata={
                            "evidence_text": sentence,
                            "section_key": sec_context["section_key"],
                            "section_number": sec_context["section_number"],
                        },
                    )
                    if rel.edge_key not in seen_edges:
                        seen_edges.add(rel.edge_key)
                        relations.append(rel)

            # Lactation statement with explicit directive
            if "allaitement" in s_low or "lait maternel" in s_low:
                has_directive = any(w in s_low for w in ["deconseill", "contre-indiqu", "prudence", "passe dans le lait", "possible", "autorise"])
                if has_directive:
                    pop_name = "Allaitement"
                    ent_id = self._register_clinical_entity(pop_name, EntityType.POPULATION, entities)
                    rel_type = (
                        RelationType.CONTRAINDICATED_FOR
                        if any(w in s_low for w in ["contre-indiqu", "ne doit pas etre utilise", "eviter"])
                        else RelationType.REQUIRES_PRECAUTION_FOR
                    )
                    rel = KGRelation(
                        source_id=primary_id,
                        target_id=ent_id,
                        relation_type=rel_type,
                        description=sentence,  # Verbatim
                        source_doc=sec_context["doc_file"],
                        confidence=1.0,
                        metadata={
                            "evidence_text": sentence,
                            "section_key": sec_context["section_key"],
                            "section_number": sec_context["section_number"],
                        },
                    )
                    if rel.edge_key not in seen_edges:
                        seen_edges.add(rel.edge_key)
                        relations.append(rel)

    def _extract_adverse_effects(
        self,
        text: str,
        primary_id: str,
        dci_entity: Optional[KGEntity],
        sec_context: Dict[str, str],
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts HAS_ADVERSE_EFFECT relationships strictly grounded in section 4.8 text."""
        lines = re.split(r"[\n•\-\*]+", text)
        for line in lines:
            item = self.clean_item_text(line)
            if not self.is_valid_clinical_item(item):
                continue

            symptoms = self.split_smart_commas(item)
            for sym in symptoms:
                if len(sym) < 3 or len(sym) > 100:
                    continue
                sym_norm = self.normalizer.clean_text(sym)
                if any(sym_norm.startswith(prefix) for prefix in MEDDRA_CLASS_PREFIXES):
                    continue

                ent_id = self._register_clinical_entity(sym, EntityType.ADVERSE_EFFECT, entities)

                rel = KGRelation(
                    source_id=primary_id,
                    target_id=ent_id,
                    relation_type=RelationType.HAS_ADVERSE_EFFECT,
                    description=sym,
                    source_doc=sec_context["doc_file"],
                    confidence=1.0,
                    metadata={
                        "evidence_text": line.strip(),
                        "section_key": sec_context["section_key"],
                        "section_number": sec_context["section_number"],
                    },
                )
                if rel.edge_key not in seen_edges:
                    seen_edges.add(rel.edge_key)
                    relations.append(rel)

    # --------------------------------------------------------------------------
    # Batch, File, and Corpus Operations
    # --------------------------------------------------------------------------

    def extract_from_file(self, file_path: Union[str, Path]) -> ExtractionResult:
        """Extracts relationships from an individual JSON monograph."""
        fpath = Path(file_path)
        if not fpath.exists():
            raise FileNotFoundError(f"File not found: {fpath}")

        with open(fpath, "r", encoding="utf-8") as f:
            doc = json.load(f)

        return self.extract_from_document(doc, doc_id=fpath.name)

    def extract_from_corpus(
        self,
        data_dir: Optional[Union[str, Path]] = None,
        dossiers: Optional[List[str]] = None,
        max_docs: Optional[int] = None,
    ) -> ExtractionResult:
        """
        Extracts and normalizes relationships across the curated pharmaceutical corpus.
        Aggregates and deduplicates entities globally across all documents.
        """
        root = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        if not root.exists():
            raise FileNotFoundError(f"Data directory not found: {root}")

        all_entities: Dict[str, KGEntity] = {}
        all_relations: List[KGRelation] = []
        seen_edges: Set[str] = set()

        json_files = sorted(root.glob("*/*/*.json"))
        doc_count = 0

        for fpath in json_files:
            if fpath.name.startswith("_"):
                continue

            file_dossier = fpath.parent.parent.name if len(fpath.parts) >= 3 else ""
            if dossiers and not any(d.lower() in file_dossier.lower() for d in dossiers):
                continue

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    doc = json.load(f)

                res = self.extract_from_document(doc, doc_id=fpath.name)
                for e in res.entities:
                    if e.id not in all_entities:
                        all_entities[e.id] = e

                for r in res.relations:
                    if r.edge_key not in seen_edges:
                        seen_edges.add(r.edge_key)
                        all_relations.append(r)

                doc_count += 1
                if max_docs and doc_count >= max_docs:
                    break
            except Exception as e:
                logger.warning("Error extracting from %s: %s", fpath, e)

        deduped_entities = self.normalizer.deduplicate_entities(all_entities.values())

        return ExtractionResult(relations=all_relations, entities=deduped_entities)

    def export_relationships(self, relations: List[KGRelation], output_file: Union[str, Path]) -> int:
        """Exports relationships to a JSONL file."""
        out = Path(output_file)
        out.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with open(out, "w", encoding="utf-8") as f:
            for r in relations:
                f.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
                count += 1
        return count

    def export_entities(self, entities: List[KGEntity], output_file: Union[str, Path]) -> int:
        """Exports entities to a JSONL file."""
        out = Path(output_file)
        out.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with open(out, "w", encoding="utf-8") as f:
            for e in entities:
                f.write(json.dumps(e.to_dict(), ensure_ascii=False) + "\n")
                count += 1
        return count

    def get_statistics(self, result: ExtractionResult) -> Dict[str, Any]:
        """Calculates breakdown and statistical summary of extracted relations and entities."""
        rel_types: Dict[str, int] = {}
        for r in result.relations:
            k = r.relation_type.value
            rel_types[k] = rel_types.get(k, 0) + 1

        ent_types: Dict[str, int] = {}
        for e in result.entities:
            k = e.entity_type.value
            ent_types[k] = ent_types.get(k, 0) + 1

        return {
            "total_entities": len(result.entities),
            "total_relationships": len(result.relations),
            "entity_breakdown": ent_types,
            "relationship_breakdown": rel_types,
        }


# Module level convenience instances
default_extractor = RelationshipExtractor()


def extract_relationships_from_document(doc: Dict[str, Any]) -> ExtractionResult:
    """Helper to extract relationships and entities from a single document."""
    return default_extractor.extract_from_document(doc)


def extract_relationships_from_corpus(
    data_dir: Optional[Union[str, Path]] = None,
    dossiers: Optional[List[str]] = None,
    max_docs: Optional[int] = None,
) -> ExtractionResult:
    """Helper to extract relationships across the corpus."""
    return default_extractor.extract_from_corpus(data_dir=data_dir, dossiers=dossiers, max_docs=max_docs)
