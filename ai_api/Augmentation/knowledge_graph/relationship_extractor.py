"""
Pharmeazor Knowledge Graph - Relationship Extractor
===================================================
Extracts high-precision clinical and structural relationships connecting
pharmaceutical entities from official monographs (ANPP, BDPM, DailyMed, Pharmnet).

Supported Relationships:
------------------------
- CONTAINS_ACTIVE_INGREDIENT : Drug -> DCI
- MANUFACTURED_BY            : Drug -> Laboratory
- HAS_DOSAGE_FORM            : Drug -> DosageForm
- TREATS                     : Drug / DCI -> Indication
- CONTRAINDICATED_FOR        : Drug / DCI -> Contraindication
- INTERACTS_WITH             : Drug / DCI -> InteractingDrug
- HAS_ADVERSE_EFFECT         : Drug / DCI -> AdverseEffect
- REQUIRES_PRECAUTION_FOR    : Drug / DCI -> Population / Condition
- HAS_MAX_DOSE               : Drug -> DosageRule
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
from ai_api.Augmentation.knowledge_graph.ontology import (
    EntityType,
    KGEntity,
    KGRelation,
    RelationType,
)

logger = logging.getLogger(__name__)

# Default location of curated corpus
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "outputs_data"

# Common boilerplate phrases to ignore
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
}


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
    Extracts clinical and pharmacological relationships from structured drug documents.
    """

    def __init__(self, confidence_threshold: float = 0.7):
        self.confidence_threshold = confidence_threshold
        self.entity_extractor = EntityExtractor()

    def clean_item_text(self, text: str) -> str:
        """Cleans bullet points, trailing references, and extra whitespace."""
        if not text:
            return ""
        # Remove leading bullet symbols
        t = re.sub(r"^[\s•\-\*\+\d\.\)\:]+", "", text).strip()
        # Remove trailing references like (voir rubrique 4.4) or (voir 6.1)
        t = re.sub(r"\(voir\s+rubrique[^\)]*\)", "", t, flags=re.I).strip()
        t = re.sub(r"\(voir[^\)]*\)", "", t, flags=re.I).strip()
        # Normalize whitespace
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def is_valid_clinical_item(self, text: str) -> bool:
        """Filters out headers, empty lines, and regulatory boilerplate."""
        if not text or len(text) < 3 or len(text) > 300:
            return False
        norm = normalize_string(text)
        for ign in IGNORE_SUBSTRINGS:
            if ign in norm:
                return False
        return True

    def extract_from_document(
        self,
        doc: Dict[str, Any],
        doc_id: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extracts all entities and relationships from a single monograph document.
        """
        entities: Dict[str, KGEntity] = {}
        relations: List[KGRelation] = []
        seen_edges: Set[str] = set()

        doc_name = (doc.get("brand") or doc.get("title") or "Unknown").strip()
        doc_source = doc.get("source", "anpp")
        doc_file = doc_id or f"{doc_name}.json"

        # 1. Extract structural entities from document metadata
        base_entities = self.entity_extractor.extract_entities_from_document(doc)
        for e in base_entities:
            entities[e.id] = e

        drug_entity = next((e for e in base_entities if e.entity_type == EntityType.DRUG), None)
        dci_entity = next((e for e in base_entities if e.entity_type == EntityType.ACTIVE_INGREDIENT), None)
        lab_entity = next((e for e in base_entities if e.entity_type == EntityType.LABORATORY), None)
        form_entity = next((e for e in base_entities if e.entity_type == EntityType.DOSAGE_FORM), None)

        # Primary subject node (prefer Drug, fallback to DCI)
        primary_id = drug_entity.id if drug_entity else (dci_entity.id if dci_entity else None)
        if not primary_id:
            return ExtractionResult()

        # 2. Structural Relationships
        # Drug -> CONTAINS_ACTIVE_INGREDIENT -> DCI
        if drug_entity and dci_entity:
            rel = KGRelation(
                source_id=drug_entity.id,
                target_id=dci_entity.id,
                relation_type=RelationType.CONTAINS_ACTIVE_INGREDIENT,
                description=f"{drug_entity.name} contient la substance active {dci_entity.name}",
                source_doc=doc_file,
                confidence=1.0,
            )
            if rel.edge_key not in seen_edges:
                seen_edges.add(rel.edge_key)
                relations.append(rel)

        # Drug -> MANUFACTURED_BY -> Laboratory
        if drug_entity and lab_entity:
            rel = KGRelation(
                source_id=drug_entity.id,
                target_id=lab_entity.id,
                relation_type=RelationType.MANUFACTURED_BY,
                description=f"{drug_entity.name} est fabriqué/exploité par {lab_entity.name}",
                source_doc=doc_file,
                confidence=1.0,
            )
            if rel.edge_key not in seen_edges:
                seen_edges.add(rel.edge_key)
                relations.append(rel)

        # Drug -> HAS_DOSAGE_FORM -> DosageForm
        if drug_entity and form_entity:
            rel = KGRelation(
                source_id=drug_entity.id,
                target_id=form_entity.id,
                relation_type=RelationType.HAS_DOSAGE_FORM,
                description=f"{drug_entity.name} se présente sous la forme {form_entity.name}",
                source_doc=doc_file,
                confidence=1.0,
            )
            if rel.edge_key not in seen_edges:
                seen_edges.add(rel.edge_key)
                relations.append(rel)

        # 3. Clinical Section Relationships
        sections = doc.get("sections", [])
        for sec in sections:
            raw_key = sec.get("key")
            sec_key = "_".join(raw_key).lower() if isinstance(raw_key, (list, tuple)) else str(raw_key or "").lower()
            sec_text = (sec.get("text") or "").strip()
            if not sec_text:
                continue

            # --- A. Indications thérapeutiques (Rubrique 4.1) ---
            if "indication" in sec_key or sec.get("number") == "4.1":
                self._extract_indications(
                    sec_text, primary_id, dci_entity, doc_file, entities, relations, seen_edges
                )

            # --- B. Posologie et règles de dose (Rubrique 4.2) ---
            elif "posolog" in sec_key or sec.get("number") == "4.2":
                self._extract_posology_rules(
                    sec_text, primary_id, doc_file, entities, relations, seen_edges
                )

            # --- C. Contre-indications (Rubrique 4.3) ---
            elif "contre_indication" in sec_key or "contraindication" in sec_key or sec.get("number") == "4.3":
                self._extract_contraindications(
                    sec_text, primary_id, dci_entity, doc_file, entities, relations, seen_edges
                )

            # --- D. Mises en garde et précautions d'emploi (Rubrique 4.4) ---
            elif "mise_en_garde" in sec_key or "precaution" in sec_key or sec.get("number") == "4.4":
                self._extract_precautions(
                    sec_text, primary_id, dci_entity, doc_file, entities, relations, seen_edges
                )

            # --- E. Interactions médicamenteuses (Rubrique 4.5) ---
            elif "interaction" in sec_key or sec.get("number") == "4.5":
                self._extract_interactions(
                    sec_text, primary_id, dci_entity, doc_file, entities, relations, seen_edges
                )

            # --- F. Fertilité, grossesse et allaitement (Rubrique 4.6) ---
            elif "fertilite" in sec_key or "grossesse" in sec_key or "pregnancy" in sec_key or sec.get("number") == "4.6":
                self._extract_pregnancy_relations(
                    sec_text, primary_id, dci_entity, doc_file, entities, relations, seen_edges
                )

            # --- G. Effets indésirables (Rubrique 4.8) ---
            elif "effet" in sec_key or "adverse" in sec_key or sec.get("number") == "4.8":
                self._extract_adverse_effects(
                    sec_text, primary_id, dci_entity, doc_file, entities, relations, seen_edges
                )

        return ExtractionResult(relations=relations, entities=list(entities.values()))

    # --------------------------------------------------------------------------
    # Specific Clinical Section Handlers
    # --------------------------------------------------------------------------

    def _extract_indications(
        self,
        text: str,
        primary_id: str,
        dci_entity: Optional[KGEntity],
        doc_file: str,
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts TREATS relationships from Indications section."""
        # Split on sentences and bullet points
        candidates = re.split(r"[\n•\-\*\;\.]+", text)
        for cand in candidates:
            item = self.clean_item_text(cand)
            if not self.is_valid_clinical_item(item):
                continue

            # Must contain therapeutic keywords or symptom descriptors
            if any(w in item.lower() for w in [
                "traitement", "indique", "douleur", "fievre", "arthrose", "migraine",
                "infection", "hypertension", "angine", "rhin", "otite", "toux", "inflamm"
            ]):
                ent_name = item.capitalize()
                ent_id = make_entity_id(EntityType.INDICATION, ent_name)
                if ent_id not in entities:
                    entities[ent_id] = self.entity_extractor.create_entity(ent_name, EntityType.INDICATION)

                # Link from primary Drug
                rel = KGRelation(
                    source_id=primary_id,
                    target_id=ent_id,
                    relation_type=RelationType.TREATS,
                    description=f"Indiqué pour : {item}",
                    source_doc=doc_file,
                    confidence=0.95,
                )
                if rel.edge_key not in seen_edges:
                    seen_edges.add(rel.edge_key)
                    relations.append(rel)

                # Also link from DCI if available
                if dci_entity and dci_entity.id != primary_id:
                    rel_dci = KGRelation(
                        source_id=dci_entity.id,
                        target_id=ent_id,
                        relation_type=RelationType.TREATS,
                        description=f"La substance {dci_entity.name} est indiquée pour : {item}",
                        source_doc=doc_file,
                        confidence=0.95,
                    )
                    if rel_dci.edge_key not in seen_edges:
                        seen_edges.add(rel_dci.edge_key)
                        relations.append(rel_dci)

    def _extract_posology_rules(
        self,
        text: str,
        primary_id: str,
        doc_file: str,
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts HAS_MAX_DOSE and posology constraint relationships."""
        # 1. Dose journalière maximale (e.g. 3000 mg par jour, 4000 mg/j)
        max_doses = re.findall(
            r"((?:dose\s+journali[eè]re\s+maximale|posologie\s+maximale|ne\s+pas\s+d[eé]passer)[^\.\n]*?(?:\d+[\s\.,]?\d*\s*(?:mg|g)\s*(?:par\s+jour|/jour|/j)?))",
            text,
            flags=re.I,
        )
        for md in max_doses:
            cleaned = self.clean_item_text(md)
            if self.is_valid_clinical_item(cleaned):
                ent_id = make_entity_id(EntityType.DOSAGE_RULE, cleaned)
                if ent_id not in entities:
                    entities[ent_id] = self.entity_extractor.create_entity(cleaned, EntityType.DOSAGE_RULE)

                rel = KGRelation(
                    source_id=primary_id,
                    target_id=ent_id,
                    relation_type=RelationType.HAS_MAX_DOSE,
                    description=cleaned,
                    source_doc=doc_file,
                    confidence=0.95,
                )
                if rel.edge_key not in seen_edges:
                    seen_edges.add(rel.edge_key)
                    relations.append(rel)

        # 2. Administration interval rule (e.g. 4 heures minimum)
        intervals = re.findall(
            r"(\b\d+\s*heures?\s*(?:minimum|d[\'\’]intervalle|entre\s*(?:chaque|deux|2)\s*prises)?)",
            text,
            flags=re.I,
        )
        for iv in intervals:
            cleaned = f"Intervalle minimum entre prises : {self.clean_item_text(iv)}"
            if self.is_valid_clinical_item(cleaned):
                ent_id = make_entity_id(EntityType.DOSAGE_RULE, cleaned)
                if ent_id not in entities:
                    entities[ent_id] = self.entity_extractor.create_entity(cleaned, EntityType.DOSAGE_RULE)

                rel = KGRelation(
                    source_id=primary_id,
                    target_id=ent_id,
                    relation_type=RelationType.HAS_MAX_DOSE,
                    description=cleaned,
                    source_doc=doc_file,
                    confidence=0.9,
                )
                if rel.edge_key not in seen_edges:
                    seen_edges.add(rel.edge_key)
                    relations.append(rel)

        # 3. Special population adaptation rules (e.g. Adulte < 50 kg, Insuffisance rénale)
        if "50 kg" in text:
            rule_text = "Dose adaptée pour patient pesant au moins 50 kg (max 4 g/j uniquement sur avis médical)"
            ent_id = make_entity_id(EntityType.DOSAGE_RULE, rule_text)
            if ent_id not in entities:
                entities[ent_id] = self.entity_extractor.create_entity(rule_text, EntityType.DOSAGE_RULE)

            rel = KGRelation(
                source_id=primary_id,
                target_id=ent_id,
                relation_type=RelationType.HAS_MAX_DOSE,
                description=rule_text,
                source_doc=doc_file,
                confidence=0.9,
            )
            if rel.edge_key not in seen_edges:
                seen_edges.add(rel.edge_key)
                relations.append(rel)

    def _extract_contraindications(
        self,
        text: str,
        primary_id: str,
        dci_entity: Optional[KGEntity],
        doc_file: str,
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts CONTRAINDICATED_FOR relationships."""
        lines = re.split(r"[\n•\-\*]+", text)
        for line in lines:
            item = self.clean_item_text(line)
            if not self.is_valid_clinical_item(item):
                continue

            ent_name = item.capitalize()
            ent_id = make_entity_id(EntityType.CONTRAINDICATION, ent_name)
            if ent_id not in entities:
                entities[ent_id] = self.entity_extractor.create_entity(ent_name, EntityType.CONTRAINDICATION)

            rel = KGRelation(
                source_id=primary_id,
                target_id=ent_id,
                relation_type=RelationType.CONTRAINDICATED_FOR,
                description=f"Contre-indiqué en cas de : {item}",
                source_doc=doc_file,
                confidence=0.95,
            )
            if rel.edge_key not in seen_edges:
                seen_edges.add(rel.edge_key)
                relations.append(rel)

            if dci_entity and dci_entity.id != primary_id:
                rel_dci = KGRelation(
                    source_id=dci_entity.id,
                    target_id=ent_id,
                    relation_type=RelationType.CONTRAINDICATED_FOR,
                    description=f"{dci_entity.name} est contre-indiqué en cas de : {item}",
                    source_doc=doc_file,
                    confidence=0.95,
                )
                if rel_dci.edge_key not in seen_edges:
                    seen_edges.add(rel_dci.edge_key)
                    relations.append(rel_dci)

    def _extract_precautions(
        self,
        text: str,
        primary_id: str,
        dci_entity: Optional[KGEntity],
        doc_file: str,
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts REQUIRES_PRECAUTION_FOR relationships."""
        lines = re.split(r"[\n•\-\*]+", text)
        for line in lines:
            item = self.clean_item_text(line)
            if not self.is_valid_clinical_item(item):
                continue

            # Detect clinical risk factor lines
            if any(w in item.lower() for w in [
                "insuffisance", "poids", "enfant", "alcool", "g6pd", "deshydratation",
                "malnutrition", "sujet age", "personne agee", "syndrome", "risque"
            ]):
                ent_name = item.capitalize()
                ent_id = make_entity_id(EntityType.POPULATION, ent_name)
                if ent_id not in entities:
                    entities[ent_id] = self.entity_extractor.create_entity(ent_name, EntityType.POPULATION)

                rel = KGRelation(
                    source_id=primary_id,
                    target_id=ent_id,
                    relation_type=RelationType.REQUIRES_PRECAUTION_FOR,
                    description=f"Précaution requise : {item}",
                    source_doc=doc_file,
                    confidence=0.9,
                )
                if rel.edge_key not in seen_edges:
                    seen_edges.add(rel.edge_key)
                    relations.append(rel)

    def _extract_interactions(
        self,
        text: str,
        primary_id: str,
        dci_entity: Optional[KGEntity],
        doc_file: str,
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts INTERACTS_WITH relationships."""
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        current_drug: Optional[str] = None
        current_desc: List[str] = []

        def flush_interaction():
            nonlocal current_drug, current_desc
            if current_drug:
                cleaned_name = self.clean_item_text(current_drug)
                if self.is_valid_clinical_item(cleaned_name):
                    ent_id = make_entity_id(EntityType.INTERACTING_DRUG, cleaned_name)
                    if ent_id not in entities:
                        entities[ent_id] = self.entity_extractor.create_entity(
                            cleaned_name, EntityType.INTERACTING_DRUG
                        )

                    desc = " ".join(current_desc).strip() or f"Interaction avec {cleaned_name}"
                    rel = KGRelation(
                        source_id=primary_id,
                        target_id=ent_id,
                        relation_type=RelationType.INTERACTS_WITH,
                        description=desc,
                        source_doc=doc_file,
                        confidence=0.95,
                    )
                    if rel.edge_key not in seen_edges:
                        seen_edges.add(rel.edge_key)
                        relations.append(rel)

                    if dci_entity and dci_entity.id != primary_id:
                        rel_dci = KGRelation(
                            source_id=dci_entity.id,
                            target_id=ent_id,
                            relation_type=RelationType.INTERACTS_WITH,
                            description=desc,
                            source_doc=doc_file,
                            confidence=0.95,
                        )
                        if rel_dci.edge_key not in seen_edges:
                            seen_edges.add(rel_dci.edge_key)
                            relations.append(rel_dci)
            current_drug = None
            current_desc = []

        for line in lines:
            # Detect interacting drug marker (e.g. '+ Antivitamines K', '• Méthotrexate', '- Lithium')
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
        doc_file: str,
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts pregnancy and lactation safety relationships."""
        t_low = text.lower()
        if "grossesse" in t_low:
            pop_name = "Femmes enceintes (Grossesse)"
            ent_id = make_entity_id(EntityType.POPULATION, pop_name)
            if ent_id not in entities:
                entities[ent_id] = self.entity_extractor.create_entity(pop_name, EntityType.POPULATION)

            rel_type = (
                RelationType.CONTRAINDICATED_FOR
                if any(w in t_low for w in ["contre-indiqu", "contre indiqu", "deconseill"])
                else RelationType.REQUIRES_PRECAUTION_FOR
            )

            rel = KGRelation(
                source_id=primary_id,
                target_id=ent_id,
                relation_type=rel_type,
                description="Information d'usage et sécurité pendant la grossesse",
                source_doc=doc_file,
                confidence=0.9,
            )
            if rel.edge_key not in seen_edges:
                seen_edges.add(rel.edge_key)
                relations.append(rel)

        if "allaitement" in t_low:
            pop_name = "Femmes allaitantes (Allaitement)"
            ent_id = make_entity_id(EntityType.POPULATION, pop_name)
            if ent_id not in entities:
                entities[ent_id] = self.entity_extractor.create_entity(pop_name, EntityType.POPULATION)

            rel = KGRelation(
                source_id=primary_id,
                target_id=ent_id,
                relation_type=RelationType.REQUIRES_PRECAUTION_FOR,
                description="Information d'usage et passage dans le lait maternel",
                source_doc=doc_file,
                confidence=0.9,
            )
            if rel.edge_key not in seen_edges:
                seen_edges.add(rel.edge_key)
                relations.append(rel)

    def _extract_adverse_effects(
        self,
        text: str,
        primary_id: str,
        dci_entity: Optional[KGEntity],
        doc_file: str,
        entities: Dict[str, KGEntity],
        relations: List[KGRelation],
        seen_edges: Set[str],
    ) -> None:
        """Extracts HAS_ADVERSE_EFFECT relationships."""
        lines = re.split(r"[\n•\-\*]+", text)
        for line in lines:
            item = self.clean_item_text(line)
            if not self.is_valid_clinical_item(item):
                continue

            # Split comma separated symptom lists (e.g. Thrombopénie, Leucopénie, Neutropénie)
            symptoms = [s.strip() for s in item.split(",") if s.strip()]
            for sym in symptoms:
                if len(sym) < 3 or len(sym) > 80:
                    continue
                # Skip MedDRA class headers (e.g. 'Affections respiratoires...')
                if sym.lower().startswith("affections "):
                    continue

                ent_name = sym.capitalize()
                ent_id = make_entity_id(EntityType.ADVERSE_EFFECT, ent_name)
                if ent_id not in entities:
                    entities[ent_id] = self.entity_extractor.create_entity(ent_name, EntityType.ADVERSE_EFFECT)

                rel = KGRelation(
                    source_id=primary_id,
                    target_id=ent_id,
                    relation_type=RelationType.HAS_ADVERSE_EFFECT,
                    description=f"Effet indésirable rapporté : {sym}",
                    source_doc=doc_file,
                    confidence=0.85,
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
        Extracts relationships across the curated pharmaceutical corpus.
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

            # Filter by dossier if specified
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

        return ExtractionResult(relations=all_relations, entities=list(all_entities.values()))

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


if __name__ == "__main__":
    import sys

    print("=" * 70)
    print("PHARMEAZOR KNOWLEDGE GRAPH - RELATIONSHIP EXTRACTOR DEMO")
    print("=" * 70)

    sample_file = DEFAULT_DATA_DIR / "01_paracetamol" / "1_1" / "001_DOLIPRANE.json"
    if not sample_file.exists():
        print(f"Sample file not found at: {sample_file}")
        sys.exit(1)

    print(f"Extracting from: {sample_file.name}")
    extractor = RelationshipExtractor()
    result = extractor.extract_from_file(sample_file)

    stats = extractor.get_statistics(result)
    print(f"\nExtracted Entities      : {stats['total_entities']}")
    print(f"Extracted Relationships : {stats['total_relationships']}")

    print("\n--- Relationship Breakdown ---")
    for r_type, cnt in sorted(stats["relationship_breakdown"].items(), key=lambda x: -x[1]):
        print(f"  - {r_type:<28} : {cnt} edges")

    print("\n--- Sample Extracted Relationships (Triples) ---")
    for r in result.relations[:12]:
        print(f"  ({r.source_id}) --[{r.relation_type.value}]--> ({r.target_id})")
        if r.description:
            print(f"      Context: {r.description[:90]}...")

    print("\n" + "=" * 70)
    print("SUCCESS: Relationship extraction completed cleanly.")
    print("=" * 70)
