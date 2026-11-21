"""
Pharmeazor RAG System - Intelligent Pharmaceutical Chunking Engine
==================================================================
Implements a state-of-the-art, domain-aware chunking strategy for Algerian
and international drug documentation (ANPP, Pharmnet DZ, BDPM, DailyMed).

Core Strategy Highlights:
------------------------
1. Section-Aware Semantic Splitting:
   Drug monographs (RCP, patient notices, SPL labels) are strictly bounded by
   clinical sections (Posology, Contraindications, Warnings, Interactions, etc.).
   Chunks never cross section boundaries to eliminate dangerous cross-clinical hallucinations.

2. Contextual Retrieval & Identity Anchoring:
   Each chunk is prepended with a structured clinical metadata header:
   [MÉDICAMENT: {brand} | DCI: {dci} | DOSAGE/FORME: {dosage_form} | LABO: {lab} | SOURCE: {source} (P{priority}) | TYPE: {doc_type} | SECTION: {title}]
   This ensures high BM25 lexical precision and dense semantic embedding alignment.

3. Adaptive Recursive Sub-Chunking:
   - Concise sections (<= max_chunk_chars) remain intact as coherent semantic units.
   - Long sections (e.g. extensive posology tables, adverse reaction catalogs)
     are partitioned recursively using hierarchy-aware separators:
     Paragraphs (\\n\\n) -> Bullet points (\\n• , \\n- ) -> Lines (\\n) -> Sentences (. ) -> Words.
   - An overlapping window (e.g. 150-200 chars) maintains continuity across boundaries.
   - Sub-chunks are tagged hierarchically (Partie X/Y).

4. Multi-Source Schema Harmonization:
   Seamlessly parses and normalizes diverse schemas from:
   - ANPP (Algerian official monographs - Priority 1)
   - Pharmnet DZ (Algerian commercial product presentations - Priority 2)
   - BDPM (French official RCP & Notices - Priority 3)
   - DailyMed (FDA SPL Drug Labels - Priority 3)

5. Standardized Clinical Classification:
   Maps varied section keys/numbers into standardized clinical categories:
   'posology', 'contraindications', 'warnings', 'interactions', 'adverse_effects',
   'overdose', 'pregnancy_lactation', 'indications', 'pharmacology', 'composition', etc.
"""

from __future__ import annotations

import csv
import glob
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Generator, Iterable, Iterator, List, Optional, Set, Tuple, Union

logger = logging.getLogger(__name__)

# Default paths - points to official outputs_data (40 DCIs, 989 monographs)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "outputs_data"
DEFAULT_PROCESSED_DIR = PROJECT_ROOT / "data" / "data" / "processed"

# Common boilerplate phrases to discard
EMPTY_SECTION_MARKERS = {
    "",
    "*(section vide)*",
    "(section vide)",
    "sans objet",
    "sans objet.",
    "non applicable",
    "non applicable.",
    "n/a",
    "none",
    "aucun",
    "aucune",
    "sans objet (voir rubrique 4.2)",
    "sans objet (voir rubrique 4.3)",
}

# Source priority lookup table
SOURCE_PRIORITIES: Dict[str, int] = {
    "anpp": 1,        # Official Algerian National Agency
    "pharmnet": 2,    # Algerian commercial market data
    "bdpm": 3,        # French official reference
    "dailymed": 3,    # US FDA SPL reference
}

# Standardized section category mappings
SECTION_CATEGORY_MAPPING: Dict[str, str] = {
    # Posology & Administration
    "posologie": "posology",
    "posologie_mode_administration": "posology",
    "dosage_and_administration": "posology",
    "dosage": "posology",
    "mode_administration": "posology",
    "4.2": "posology",

    # Contraindications
    "contre_indications": "contraindications",
    "contre-indications": "contraindications",
    "contraindications": "contraindications",
    "4.3": "contraindications",

    # Warnings & Precautions
    "mises_en_garde": "warnings",
    "mises_en_garde_et_precautions_d_emploi": "warnings",
    "warnings_and_precautions": "warnings",
    "boxed_warning": "warnings",
    "precautions": "warnings",
    "warnings": "warnings",
    "4.4": "warnings",

    # Drug Interactions
    "interactions": "interactions",
    "interactions_medicamenteuses": "interactions",
    "drug_interactions": "interactions",
    "4.5": "interactions",

    # Adverse Reactions
    "effets_indesirables": "adverse_effects",
    "effets_secondaires": "adverse_effects",
    "adverse_reactions": "adverse_effects",
    "4.8": "adverse_effects",

    # Overdose
    "surdosage": "overdose",
    "overdosage": "overdose",
    "intoxication": "overdose",
    "4.9": "overdose",

    # Pregnancy & Lactation
    "fertilite_grossesse": "pregnancy_lactation",
    "grossesse": "pregnancy_lactation",
    "pregnancy": "pregnancy_lactation",
    "pregnancy_and_lactation": "pregnancy_lactation",
    "allaitement": "pregnancy_lactation",
    "fertility": "pregnancy_lactation",
    "4.6": "pregnancy_lactation",

    # Indications
    "indications": "indications",
    "indications_therapeutiques": "indications",
    "indications_and_usage": "indications",
    "usage": "indications",
    "4.1": "indications",

    # Pharmacology
    "pharmacodynamie": "pharmacology",
    "pharmacocinetique": "pharmacology",
    "proprietes_pharmacologiques": "pharmacology",
    "clinical_pharmacology": "pharmacology",
    "mechanism_of_action": "pharmacology",
    "pharmacokinetics": "pharmacology",
    "pharmacodynamics": "pharmacology",
    "microbiology": "pharmacology",
    "5.1": "pharmacology",
    "5.2": "pharmacology",
    "5.3": "pharmacology",

    # Composition & Form
    "composition": "composition",
    "excipients": "composition",
    "forme_pharmaceutique": "composition",
    "description": "composition",
    "how_supplied": "composition",
    "presentation": "composition",
    "dosage_forms_and_strengths": "composition",
    "2": "composition",
    "3": "composition",
    "6.1": "composition",

    # Administrative & Identification
    "denomination": "identification",
    "nom_commercial": "identification",
    "dci": "identification",
    "titulaire": "administrative",
    "amm": "administrative",
    "numero_autorisation": "administrative",
    "conservation": "administrative",
    "conditions_delivrance": "administrative",
    "1": "identification",
    "7": "administrative",
    "8": "administrative",
}


@dataclass
class ChunkingConfig:
    """
    Configuration parameters for pharmaceutical text chunking.
    """
    min_chunk_chars: int = 50           # Discard fragments shorter than this
    max_chunk_chars: int = 1400         # Upper character boundary before recursive splitting
    overlap_chars: int = 180            # Overlap between consecutive sub-chunks of the same section
    add_context_header: bool = True     # Whether to prepend contextual metadata header
    header_style: str = "full"          # 'full', 'compact', or 'none'
    clean_whitespace: bool = True       # Clean extra blank lines and line breaks
    clinical_only: bool = False         # Only keep clinical sections (posology, contraindications, etc.)
    include_product_cards: bool = True  # Include commercial product cards (e.g. Pharmnet DZ)
    min_tokens_estimate_factor: float = 0.25 # Approx 4 chars per token


@dataclass
class DrugChunk:
    """
    Represents an atomic, embeddable chunk enriched with pharmaceutical metadata.
    """
    chunk_id: str
    text: str                  # Contextual header + chunk content (ready for embedding/retrieval)
    content: str               # Raw content without header (for display or generation prompt)
    header: str                # Contextual header alone
    metadata: Dict[str, Any]   # Structured metadata for filtering in Vector DB

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to standard dictionary."""
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "content": self.content,
            "header": self.header,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Serialize chunk to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_qdrant_point(self) -> Dict[str, Any]:
        """Return format suitable for Qdrant payload."""
        return {
            "id": self.chunk_id,
            "payload": {
                "text": self.text,
                "content": self.content,
                "header": self.header,
                **self.metadata,
            }
        }


def clean_text(text: str) -> str:
    """
    Cleans raw document text by removing web scrap residues, collapsing
    multiple newlines and carriage returns, and stripping trailing whitespace.
    """
    if not text:
        return ""
    # Normalize carriage returns
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove web scraping anchors found in BDPM
    text = re.sub(r"Redirection vers le haut de page", "", text, flags=re.IGNORECASE)
    # Remove repeated excessive dots or underscores (e.g. form lines: "Paracétamol ....... 1000 mg")
    text = re.sub(r"\.{4,}", "...", text)
    # Collapse multiple blank lines to at most two
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Strip whitespace
    return text.strip()


def normalize_section_key(raw_key: Any) -> str:
    """
    Normalizes a section key whether it is a string, a list, or None.
    Handles DailyMed list keys like ['indications', 'Indications and Usage'].
    """
    if raw_key is None:
        return ""
    if isinstance(raw_key, (list, tuple)):
        # Join non-empty string components
        parts = [str(k).strip() for k in raw_key if str(k).strip()]
        raw_key = "_".join(parts)
    k_str = str(raw_key).strip().lower()
    # Normalize slashes, hyphens, and spaces to underscores
    k_str = re.sub(r"[\s\-\/\.]+", "_", k_str)
    return k_str


def categorize_section(section_key: str, section_number: Optional[str] = None, section_title: Optional[str] = None) -> str:
    """
    Categorizes a section into a canonical clinical class:
    posology, contraindications, warnings, interactions, adverse_effects,
    overdose, pregnancy_lactation, indications, pharmacology, composition,
    identification, administrative, or other.
    """
    norm_key = normalize_section_key(section_key)
    norm_num = (section_number or "").strip()
    norm_title = (section_title or "").strip().lower()

    # 1. Exact match by normalized number
    if norm_num in SECTION_CATEGORY_MAPPING:
        return SECTION_CATEGORY_MAPPING[norm_num]

    # 2. Exact match on normalized key
    if norm_key in SECTION_CATEGORY_MAPPING:
        return SECTION_CATEGORY_MAPPING[norm_key]

    # 3. Substring matching on key and title
    combined = f"{norm_key} {norm_title}"

    if any(w in combined for w in ["posolog", "dosage", "administration", "mode d'emploi", "comment prendre"]):
        return "posology"
    if any(w in combined for w in ["contre_indication", "contre-indication", "contraindication", "ne pas prendre"]):
        return "contraindications"
    if any(w in combined for w in ["mise_en_garde", "mises en garde", "precaution", "avertissement", "warning", "boxed"]):
        return "warnings"
    if any(w in combined for w in ["interaction", "interactions médicamenteuses", "drug interaction"]):
        return "interactions"
    if any(w in combined for w in ["effet_indesirable", "effets indésirables", "adverse reaction", "side effect"]):
        return "adverse_effects"
    if any(w in combined for w in ["surdosage", "overdose", "overdosage", "intoxication"]):
        return "overdose"
    if any(w in combined for w in ["grossesse", "allaitement", "fertilite", "pregnancy", "lactation", "fertility"]):
        return "pregnancy_lactation"
    if any(w in combined for w in ["indication", "usage", "dans quel cas"]):
        return "indications"
    if any(w in combined for w in ["pharmacodynam", "pharmacocinet", "pharmacology", "mecanisme"]):
        return "pharmacology"
    if any(w in combined for w in ["composition", "excipient", "forme", "presentation", "conditionnement", "description"]):
        return "composition"
    if any(w in combined for w in ["titulaire", "fabricant", "amm", "conservation", "administrative", "delivrance"]):
        return "administrative"
    if any(w in combined for w in ["denomination", "nom commercial", "dci", "identification"]):
        return "identification"

    return "other"


def is_clinical_category(category: str) -> bool:
    """Return True if category contains clinical/medical decision support information."""
    return category in {
        "posology",
        "contraindications",
        "warnings",
        "interactions",
        "adverse_effects",
        "overdose",
        "pregnancy_lactation",
        "indications",
        "pharmacology",
    }


class RecursiveSemanticSplitter:
    """
    Splits long section text recursively preserving paragraph, list item,
    and sentence boundaries, while maintaining an overlapping window.
    """

    DEFAULT_SEPARATORS: List[str] = [
        "\n\n",       # Paragraphs
        "\n• ",       # Bullet points (bullet)
        "\n- ",       # Bullet points (dash)
        "\n* ",       # Markdown bullets
        "\n",         # Table rows and line breaks
        ". ",         # Sentence boundaries
        "; ",         # Semi-colon clauses
        ", ",         # Comma clauses
        " ",          # Word boundaries
        "",           # Character boundary fallback
    ]

    def __init__(self, max_chars: int = 1400, overlap_chars: int = 180, separators: Optional[List[str]] = None):
        self.max_chars = max(max_chars, 200)
        self.overlap_chars = max(min(overlap_chars, self.max_chars // 2), 0)
        self.separators = separators or self.DEFAULT_SEPARATORS

    def split_text(self, text: str) -> List[str]:
        """
        Recursively splits text into chunks of at most `max_chars`,
        attempting to split at the highest-level natural separator first.
        """
        text = text.strip()
        if not text:
            return []

        if len(text) <= self.max_chars:
            return [text]

        return self._recursive_split(text, self.separators)

    def _recursive_split(self, text: str, separators: List[str]) -> List[str]:
        if len(text) <= self.max_chars:
            return [text]

        if not separators:
            # Fallback hard slice with overlap
            chunks: List[str] = []
            start = 0
            while start < len(text):
                end = min(start + self.max_chars, len(text))
                chunks.append(text[start:end].strip())
                if end == len(text):
                    break
                start += self.max_chars - self.overlap_chars
            return [c for c in chunks if c]

        sep = separators[0]
        remaining_seps = separators[1:]

        if sep == "":
            splits = list(text)
        else:
            splits = text.split(sep)

        # Merge splits into windows <= max_chars
        merged_chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for part in splits:
            part_len = len(part) + (len(sep) if current_chunk else 0)

            if part_len > self.max_chars:
                # If current accumulator has content, flush it
                if current_chunk:
                    merged = sep.join(current_chunk).strip()
                    if merged:
                        merged_chunks.append(merged)
                    current_chunk = []
                    current_len = 0

                # Recursively split this single oversized part with next separator
                sub_splits = self._recursive_split(part, remaining_seps)
                merged_chunks.extend(sub_splits)
            elif current_len + part_len <= self.max_chars:
                current_chunk.append(part)
                current_len += part_len
            else:
                # Chunk is full, record it
                merged = sep.join(current_chunk).strip()
                if merged:
                    merged_chunks.append(merged)

                # Implement overlap by carrying over trailing context
                overlap_seed: List[str] = []
                overlap_len = 0
                if self.overlap_chars > 0 and current_chunk:
                    for prev_part in reversed(current_chunk):
                        if overlap_len + len(prev_part) <= self.overlap_chars:
                            overlap_seed.insert(0, prev_part)
                            overlap_len += len(prev_part) + len(sep)
                        else:
                            break

                current_chunk = overlap_seed + [part]
                current_len = sum(len(p) for p in current_chunk) + len(sep) * max(0, len(current_chunk) - 1)

        if current_chunk:
            merged = sep.join(current_chunk).strip()
            if merged:
                merged_chunks.append(merged)

        return merged_chunks


def build_context_header(
    brand: str,
    dci: str,
    dosage_form: str,
    lab: str,
    source: str,
    priority: int,
    doc_type: str,
    section_title: str,
    section_number: str = "",
    part_idx: Optional[int] = None,
    total_parts: Optional[int] = None,
    style: str = "full",
) -> str:
    """
    Builds a standardized pharmaceutical context header.

    Example:
    [MÉDICAMENT: DOLIPRANE | DCI: PARACÉTAMOL | DOSAGE/FORME: 1000 mg, comprimé | LABO: PROPHARMAL SPA | SOURCE: anpp (P1) | TYPE: rcp | SECTION: 4.2 Posologie et mode d'administration]
    """
    if style == "none":
        return ""

    source_label = source.upper() if source else "UNKNOWN"
    doc_type_label = doc_type.upper() if doc_type else "DOC"

    # Assemble section designation
    sec_parts = []
    if section_number:
        sec_parts.append(str(section_number).strip())
    if section_title:
        sec_parts.append(str(section_title).strip())
    sec_display = " ".join(sec_parts) if sec_parts else "Informations Générales"

    part_suffix = ""
    if part_idx is not None and total_parts is not None and total_parts > 1:
        part_suffix = f" [Partie {part_idx}/{total_parts}]"

    if style == "compact":
        items = []
        if brand:
            items.append(f"{brand}")
        if dci and dci != brand:
            items.append(f"({dci})")
        if dosage_form:
            items.append(f"{dosage_form}")
        items.append(f"[{source_label} P{priority}]")
        items.append(f"§ {sec_display}{part_suffix}")
        return " | ".join(items)

    # Full standard style
    elements = []
    if brand:
        elements.append(f"MÉDICAMENT: {brand}")
    if dci:
        elements.append(f"DCI: {dci}")
    if dosage_form:
        elements.append(f"FORME/DOSAGE: {dosage_form}")
    if lab:
        elements.append(f"LABO: {lab}")

    elements.append(f"SOURCE: {source_label} (P{priority})")
    elements.append(f"TYPE: {doc_type_label}")
    elements.append(f"SECTION: {sec_display}{part_suffix}")

    return f"[{' | '.join(elements)}]"


def generate_chunk_id(source: str, drug_id: Any, brand: str, sec_key: str, part: int, content_snippet: str, filename : str = '') -> str:
    """Generates a deterministic unique chunk ID."""
    raw = f"{source}_{drug_id}_{brand}_{sec_key}_{part}_{filename}_{content_snippet[:40]}"
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    clean_sec = re.sub(r"[^a-zA-Z0-9_]", "", str(sec_key))[:12]
    return f"chk_{source}_{clean_sec}_{part}_{h}"


class DrugChunker:
    """
    Production-grade chunking processor for Pharmeazor drug data.
    Takes documents from ANPP, Pharmnet DZ, BDPM, and DailyMed, and produces
    RAG-ready, contextually anchored, section-aware chunks.
    """

    def __init__(self, config: Optional[ChunkingConfig] = None):
        self.config = config or ChunkingConfig()
        self.splitter = RecursiveSemanticSplitter(
            max_chars=self.config.max_chunk_chars,
            overlap_chars=self.config.overlap_chars,
        )

    def chunk_document(
        self,
        doc: Dict[str, Any],
        dossier: Optional[str] = None,
        file_name: Optional[str] = None,
    ) -> List[DrugChunk]:
        """
        Chunks an individual document according to its source, type, and sections.
        """
        source = (doc.get("source") or "unknown").lower()
        source_priority = int(doc.get("source_priority") or SOURCE_PRIORITIES.get(source, 3))
        drug_id = doc.get("drug_id")
        brand = (doc.get("brand") or doc.get("title") or "").strip()
        dci = (doc.get("dci") or "").strip()
        lab = (doc.get("lab") or doc.get("manufacturer") or "").strip()
        doc_type = (doc.get("doc_type") or "document").lower()
        url = doc.get("url") or doc.get("source_url") or ""
        language = doc.get("language") or "fr"
        doc_dossier = dossier or doc.get("dossier") or ""
        doc_file_name = file_name or doc.get("file_name") or ""

        # Determine dosage and pharmaceutical form from document fields
        form = doc.get("form") or ""
        dosage = doc.get("dosage") or ""
        cond = doc.get("conditionnement") or ""

        dosage_form_parts = [p for p in [dosage, form, cond] if p]
        dosage_form = " ".join(dosage_form_parts).strip()

        # Extra metadata for commercial product cards (e.g. Pharmnet)
        reg_number = doc.get("reg_number")
        price_ppa = doc.get("price_ppa")

        sections = doc.get("sections", [])
        chunks: List[DrugChunk] = []

        # Case 1: Structured sections exist
        valid_sections = []
        for s in sections:
            t = clean_text(s.get("text", ""))
            if not t or t.lower() in EMPTY_SECTION_MARKERS:
                continue
            if len(t) < self.config.min_chunk_chars:
                continue
            valid_sections.append((s, t))

        if valid_sections:
            for sec_dict, sec_text in valid_sections:
                raw_key = sec_dict.get("key")
                sec_key = normalize_section_key(raw_key)
                sec_num = str(sec_dict.get("number") or "").strip()
                sec_title = str(sec_dict.get("title") or sec_dict.get("label") or sec_key).strip()

                category = categorize_section(sec_key, sec_num, sec_title)

                # Clinical-only filtering if requested
                if self.config.clinical_only and not is_clinical_category(category):
                    continue

                # Split section text adaptively
                sub_texts = self.splitter.split_text(sec_text)
                total_parts = len(sub_texts)

                for part_idx, part_content in enumerate(sub_texts, start=1):
                    if len(part_content) < self.config.min_chunk_chars:
                        continue

                    # Build context header
                    header = build_context_header(
                        brand=brand,
                        dci=dci,
                        dosage_form=dosage_form,
                        lab=lab,
                        source=source,
                        priority=source_priority,
                        doc_type=doc_type,
                        section_title=sec_title,
                        section_number=sec_num,
                        part_idx=part_idx if total_parts > 1 else None,
                        total_parts=total_parts if total_parts > 1 else None,
                        style=self.config.header_style,
                    )

                    full_text = f"{header}\n\n{part_content}" if header else part_content

                    chunk_id = generate_chunk_id(source, drug_id, brand, sec_key, part_idx, part_content, doc_file_name)

                    metadata: Dict[str, Any] = {
                        "drug_id": drug_id,
                        "brand": brand,
                        "dci": dci,
                        "lab": lab,
                        "dosage_form": dosage_form,
                        "form": form,
                        "dosage": dosage,
                        "source": source,
                        "source_priority": source_priority,
                        "doc_type": doc_type,
                        "url": url,
                        "language": language,
                        "dossier": doc_dossier,
                        "file_name": doc_file_name,
                        "section_key": sec_key,
                        "section_category": category,
                        "section_number": sec_num,
                        "section_title": sec_title,
                        "chunk_part": part_idx,
                        "total_parts": total_parts,
                        "is_split": total_parts > 1,
                        "char_count": len(full_text),
                        "word_count": len(full_text.split()),
                    }

                    if reg_number:
                        metadata["reg_number"] = reg_number
                    if price_ppa is not None:
                        metadata["price_ppa"] = price_ppa

                    chunks.append(
                        DrugChunk(
                            chunk_id=chunk_id,
                            text=full_text,
                            content=part_content,
                            header=header,
                            metadata=metadata,
                        )
                    )

        # Case 2: Document has no valid sections but has top-level text (e.g. Pharmnet fiches or raw notes)
        elif doc.get("text"):
            raw_doc_text = clean_text(doc.get("text", ""))
            if len(raw_doc_text) >= self.config.min_chunk_chars:
                category = "product_overview" if doc_type == "fiche_produit" else "general"

                if not (self.config.clinical_only and category == "product_overview"):
                    sub_texts = self.splitter.split_text(raw_doc_text)
                    total_parts = len(sub_texts)

                    for part_idx, part_content in enumerate(sub_texts, start=1):
                        header = build_context_header(
                            brand=brand,
                            dci=dci,
                            dosage_form=dosage_form,
                            lab=lab,
                            source=source,
                            priority=source_priority,
                            doc_type=doc_type,
                            section_title="Fiche Produit" if doc_type == "fiche_produit" else "Notice / Document",
                            part_idx=part_idx if total_parts > 1 else None,
                            total_parts=total_parts if total_parts > 1 else None,
                            style=self.config.header_style,
                        )

                        full_text = f"{header}\n\n{part_content}" if header else part_content
                        chunk_id = generate_chunk_id(source, drug_id, brand, "overview", part_idx, part_content, doc_file_name)

                        metadata = {
                            "drug_id": drug_id,
                            "brand": brand,
                            "dci": dci,
                            "lab": lab,
                            "dosage_form": dosage_form,
                            "form": form,
                            "dosage": dosage,
                            "source": source,
                            "source_priority": source_priority,
                            "doc_type": doc_type,
                            "url": url,
                            "language": language,
                            "dossier": doc_dossier,
                            "file_name": doc_file_name,
                            "section_key": "overview",
                            "section_category": category,
                            "section_number": "",
                            "section_title": "Présentation du Produit",
                            "chunk_part": part_idx,
                            "total_parts": total_parts,
                            "is_split": total_parts > 1,
                            "char_count": len(full_text),
                            "word_count": len(full_text.split()),
                        }

                        if reg_number:
                            metadata["reg_number"] = reg_number
                        if price_ppa is not None:
                            metadata["price_ppa"] = price_ppa

                        chunks.append(
                            DrugChunk(
                                chunk_id=chunk_id,
                                text=full_text,
                                content=part_content,
                                header=header,
                                metadata=metadata,
                            )
                        )

        return chunks

    def chunk_json_file(self, file_path: Union[str, Path]) -> List[DrugChunk]:
        """
        Loads and chunks an individual .json pharmaceutical monograph.
        Automatically infers dossier and file_name from the file path.
        """
        fpath = Path(file_path)
        if not fpath.exists():
            raise FileNotFoundError(f"File not found: {fpath}")

        with open(fpath, "r", encoding="utf-8") as f:
            doc = json.load(f)

        # In outputs_data, path is: outputs_data/<dossier>/<sub_folder>/<file>.json
        dossier = None
        if len(fpath.parts) >= 3:
            candidate = fpath.parent.parent.name
            if candidate and not candidate.startswith("."):
                dossier = candidate

        return self.chunk_document(doc, dossier=dossier, file_name=fpath.name)

    def chunk_jsonl_file(self, file_path: Union[str, Path]) -> Iterator[DrugChunk]:
        """
        Yields chunks from a JSONL file one line at a time (memory efficient).
        """
        fpath = Path(file_path)
        if not fpath.exists():
            raise FileNotFoundError(f"File not found: {fpath}")

        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    doc = json.loads(line)
                    for chunk in self.chunk_document(doc, file_name=fpath.name):
                        yield chunk
                except json.JSONDecodeError as e:
                    logger.warning("Error parsing JSON line in %s: %s", fpath, e)

    def chunk_directory(
        self,
        dir_path: Union[str, Path],
        dossier: Optional[str] = None,
        sources: Optional[List[str]] = None,
        drug_ids: Optional[List[int]] = None,
        doc_type: Optional[str] = None,
        brand: Optional[str] = None,
        dci: Optional[str] = None,
        max_docs: Optional[int] = None,
    ) -> Iterator[DrugChunk]:
        """
        Walks a directory or subfolders, finds .json monographs (data/outputs_data)
        and .jsonl files, yielding DrugChunk instances.
        Skips control and summary files prefixed with '_'.
        """
        root = Path(dir_path)
        if not root.exists():
            raise FileNotFoundError(f"Directory not found: {root}")

        json_files = sorted(root.glob("**/*.json"))
        jsonl_files = sorted(root.glob("**/*.jsonl"))

        doc_count = 0
        dossier_lower = dossier.lower() if dossier else None
        brand_lower = brand.lower() if brand else None
        dci_lower = dci.lower() if dci else None
        doc_type_lower = doc_type.lower() if doc_type else None

        # 1. Process individual .json files (data/outputs_data monographs)
        for fpath in json_files:
            if fpath.name.startswith("_"):
                continue

            file_dossier = fpath.parent.parent.name if len(fpath.parts) >= 3 else ""
            if dossier_lower and dossier_lower not in file_dossier.lower():
                continue

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    doc = json.load(f)

                if drug_ids and doc.get("drug_id") not in drug_ids:
                    continue
                if sources and (doc.get("source") or "").lower() not in [s.lower() for s in sources]:
                    continue
                if doc_type_lower and (doc.get("doc_type") or "").lower() != doc_type_lower:
                    continue
                if brand_lower and brand_lower not in (doc.get("brand") or "").lower():
                    continue
                if dci_lower and dci_lower not in (doc.get("dci") or "").lower():
                    continue

                for chunk in self.chunk_document(doc, dossier=file_dossier, file_name=fpath.name):
                    yield chunk

                doc_count += 1
                if max_docs and doc_count >= max_docs:
                    return
            except Exception as e:
                logger.warning("Error processing %s: %s", fpath, e)

        # 2. Process .jsonl files (if present in the targeted directory)
        for fpath in jsonl_files:
            if fpath.name.startswith("_"):
                continue

            if dossier_lower and dossier_lower not in fpath.name.lower():
                continue

            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        doc = json.loads(line)
                        if drug_ids and doc.get("drug_id") not in drug_ids:
                            continue
                        if sources and (doc.get("source") or "").lower() not in [s.lower() for s in sources]:
                            continue
                        if doc_type_lower and (doc.get("doc_type") or "").lower() != doc_type_lower:
                            continue
                        if brand_lower and brand_lower not in (doc.get("brand") or "").lower():
                            continue
                        if dci_lower and dci_lower not in (doc.get("dci") or "").lower():
                            continue

                        for chunk in self.chunk_document(doc, file_name=fpath.name):
                            yield chunk

                        doc_count += 1
                        if max_docs and doc_count >= max_docs:
                            return
            except Exception as e:
                logger.warning("Error processing line in %s: %s", fpath, e)

    def export_to_jsonl(self, chunks: Iterable[DrugChunk], output_file: Union[str, Path]) -> int:
        """
        Exports an iterable of chunks to a JSONL file.
        Returns total count of chunks written.
        """
        out = Path(output_file)
        out.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with open(out, "w", encoding="utf-8") as f:
            for chk in chunks:
                f.write(chk.to_json() + "\n")
                count += 1
        return count

    def get_statistics(self, chunks: List[DrugChunk]) -> Dict[str, Any]:
        """
        Computes statistical summary of generated chunks.
        """
        if not chunks:
            return {"total_chunks": 0}

        lengths = [len(c.text) for c in chunks]
        sources: Dict[str, int] = {}
        categories: Dict[str, int] = {}
        doc_types: Dict[str, int] = {}
        split_count = 0

        for c in chunks:
            s = c.metadata.get("source", "unknown")
            sources[s] = sources.get(s, 0) + 1

            cat = c.metadata.get("section_category", "other")
            categories[cat] = categories.get(cat, 0) + 1

            dt = c.metadata.get("doc_type", "unknown")
            doc_types[dt] = doc_types.get(dt, 0) + 1

            if c.metadata.get("is_split"):
                split_count += 1

        return {
            "total_chunks": len(chunks),
            "split_chunks_count": split_count,
            "avg_char_length": round(sum(lengths) / len(lengths), 1),
            "min_char_length": min(lengths),
            "max_char_length": max(lengths),
            "sources_breakdown": sources,
            "categories_breakdown": categories,
            "doc_types_breakdown": doc_types,
        }


# Convenience module-level instances & functions
default_chunker = DrugChunker()


def chunk_document(
    doc: Dict[str, Any],
    dossier: Optional[str] = None,
    file_name: Optional[str] = None,
    config: Optional[ChunkingConfig] = None,
) -> List[DrugChunk]:
    """Helper to chunk a single document dictionary."""
    chunker = DrugChunker(config) if config else default_chunker
    return chunker.chunk_document(doc, dossier=dossier, file_name=file_name)


def chunk_file(file_path: Union[str, Path], config: Optional[ChunkingConfig] = None) -> List[DrugChunk]:
    """Helper to chunk any pharmaceutical document file (.json monograph or .jsonl lines)."""
    chunker = DrugChunker(config) if config else default_chunker
    fpath = Path(file_path)
    if fpath.suffix.lower() == ".json":
        return chunker.chunk_json_file(fpath)
    return list(chunker.chunk_jsonl_file(fpath))


def chunk_corpus(
    data_dir: Optional[Union[str, Path]] = None,
    dossier: Optional[str] = None,
    sources: Optional[List[str]] = None,
    drug_ids: Optional[List[int]] = None,
    doc_type: Optional[str] = None,
    brand: Optional[str] = None,
    dci: Optional[str] = None,
    config: Optional[ChunkingConfig] = None,
    max_docs: Optional[int] = None,
) -> Iterator[DrugChunk]:
    """
    Helper to stream chunks from the curated corpus directory (data/outputs_data by default).
    """
    target_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    chunker = DrugChunker(config) if config else default_chunker
    return chunker.chunk_directory(
        target_dir,
        dossier=dossier,
        sources=sources,
        drug_ids=drug_ids,
        doc_type=doc_type,
        brand=brand,
        dci=dci,
        max_docs=max_docs,
    )


# Backward-compatibility alias
chunk_processed_corpus = chunk_corpus


def get_all_dossiers(data_dir: Optional[Union[str, Path]] = None) -> List[str]:
    """Return sorted list of all DCI dossier folders in outputs_data (e.g. 01_paracetamol)."""
    target_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    if not target_dir.exists():
        return []
    dossiers = [d.name for d in target_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]
    return sorted(dossiers)
