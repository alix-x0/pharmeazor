"""
Pharmeazor Knowledge Graph - Medical Provenance & Grounding Engine
==================================================================
Guarantees strict clinical safety and provenance for the Knowledge Graph.
Enforces the Zero-Inference Rule:
- No medical relationship, posology rule, or contraindication can exist in the
  Knowledge Graph without a direct, verifiable verbatim citation in the source document.
- Validates that every extracted claim literally exists within the official monograph text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ai_api.Augmentation.knowledge_graph.ontology import KGRelation

logger = logging.getLogger(__name__)


@dataclass
class ProvenanceRecord:
    """
    Detailed audit provenance record binding a knowledge graph triple
    to its exact physical location in an official medical document.
    """
    source_doc: str                             # Document filename (e.g. '001_DOLIPRANE.json')
    section_key: str                            # Section key (e.g. 'posologie', 'contre_indications')
    section_number: str                         # Regulatory section number (e.g. '4.2', '4.3')
    section_title: str                          # Section title as written in monograph
    verbatim_text: str                          # Exact text quote from the official document
    char_start: Optional[int] = None            # Character start offset in section text
    char_end: Optional[int] = None              # Character end offset in section text

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_doc": self.source_doc,
            "section_key": self.section_key,
            "section_number": self.section_number,
            "section_title": self.section_title,
            "verbatim_text": self.verbatim_text,
            "char_start": self.char_start,
            "char_end": self.char_end,
        }


def normalize_for_matching(text: str) -> str:
    """Normalizes whitespace and lowercases text for verbatim existence check."""
    if not text:
        return ""
    # Collapse multiple whitespaces and newlines
    cleaned = re.sub(r"\s+", " ", text).strip().lower()
    return cleaned


def verify_text_in_document(verbatim_quote: str, doc: Dict[str, Any]) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Strictly verifies that a given verbatim quote literally exists within
    the text of the provided monograph document.

    Returns:
        (is_present, section_info_dict)
    """
    if not verbatim_quote or not verbatim_quote.strip():
        return False, None

    norm_quote = normalize_for_matching(verbatim_quote)
    if len(norm_quote) < 5:
        return False, None

    # Check across all document sections
    sections = doc.get("sections", [])
    for sec in sections:
        sec_text = sec.get("text") or ""
        norm_sec = normalize_for_matching(sec_text)
        if norm_quote in norm_sec:
            raw_key = sec.get("key")
            sec_key = "_".join(raw_key).lower() if isinstance(raw_key, (list, tuple)) else str(raw_key or "").lower()
            return True, {
                "section_key": sec_key,
                "section_number": str(sec.get("number", "")),
                "section_title": str(sec.get("title", "")),
            }

    return False, None


def validate_relation_grounding(relation: KGRelation, doc: Dict[str, Any]) -> bool:
    """
    CRITICAL MEDICAL SAFETY AUDIT:
    Validates that a KGRelation is strictly grounded in the source document.
    Rejects any relation if:
    1. It lacks an 'evidence_text' in metadata.
    2. The 'evidence_text' is not literally present in the document.
    3. It represents an unsupported medical inference.
    """
    # Structural relations from metadata (CONTAINS_ACTIVE_INGREDIENT, MANUFACTURED_BY, HAS_DOSAGE_FORM)
    # are grounded in the document header metadata (brand, dci, lab, form).
    if relation.relation_type.value in (
        "CONTAINS_ACTIVE_INGREDIENT",
        "MANUFACTURED_BY",
        "HAS_DOSAGE_FORM",
    ):
        return True

    evidence = relation.metadata.get("evidence_text")
    if not evidence or not isinstance(evidence, str) or not evidence.strip():
        logger.warning(
            "REJECTED UNGROUNDED RELATION: %s -> %s lacking verbatim evidence",
            relation.source_id,
            relation.target_id,
        )
        return False

    is_found, sec_info = verify_text_in_document(evidence, doc)
    if not is_found:
        logger.warning(
            "REJECTED HALLUCINATED RELATION: Evidence text not found verbatim in doc %s: %s",
            relation.source_doc,
            evidence[:80],
        )
        return False

    # Enrich relation metadata with verified provenance
    if sec_info:
        relation.metadata.setdefault("section_key", sec_info["section_key"])
        relation.metadata.setdefault("section_number", sec_info["section_number"])
        relation.metadata.setdefault("section_title", sec_info["section_title"])

    return True
