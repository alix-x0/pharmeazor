"""
Pharmeazor Drug Corpus Loader & RAG Data Layer
==============================================
Provides structured access, parsing, filtering, and chunking for the
curated Algerian ANPP pharmaceutical monographs dataset (40 DCI classes, 989 documents).

Usage:
    from data.loader import DrugCorpusLoader

    loader = DrugCorpusLoader()
    print(f"Total documents: {len(loader)}")

    # Get RAG-ready chunks with medical metadata
    chunks = loader.get_rag_chunks(min_chars=50)
    print(f"Total RAG chunks: {len(chunks)}")
    print(chunks[0].text)
    print(chunks[0].metadata)
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Generator, Iterator, List, Optional, Set

logger = logging.getLogger(__name__)

# Default location of the dataset inside the project
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "outputs_data"


@dataclass
class Section:
    """Represents a specific clinical/regulatory section in a drug monograph."""
    key: str
    label: str
    number: str
    title: str
    text: str

    def is_empty(self) -> bool:
        t = self.text.strip()
        return not t or t.lower() in {"*(section vide)*", "sans objet", "non applicable", "sans objet."}


@dataclass
class DrugDocument:
    """Represents a complete pharmaceutical monograph (RCP or Notice)."""
    file_path: Path
    dossier: str
    brand: str
    dci: str
    lab: str
    source: str
    source_priority: int
    doc_type: str  # 'rcp' or 'notice'
    match_type: str
    language: str
    url: str
    title: str
    text: str
    sections: List[Section] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict, repr=False)

    def get_section(self, key: str) -> Optional[Section]:
        """Retrieve a specific section by key (e.g. 'interactions', 'contre_indications')."""
        for s in self.sections:
            if s.key == key:
                return s
        return None

    def get_clinical_sections(self) -> List[Section]:
        """Return non-empty clinical sections relevant for medical queries."""
        clinical_keys = {
            "indications",
            "posologie",
            "contre_indications",
            "mises_en_garde",
            "interactions",
            "fertilite_grossesse",
            "effets_indesirables",
            "surdosage",
            "pharmacodynamie",
            "pharmacocinetique",
            "donnees_securite",
        }
        return [s for s in self.sections if s.key in clinical_keys and not s.is_empty()]


@dataclass
class RAGChunk:
    """A chunk ready to be embedded into a vector database (Chroma, FAISS, Qdrant, etc.)."""
    text: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "metadata": self.metadata,
        }


class DrugCorpusLoader:
    """
    Loader and preprocessor for the Pharmeazor drug corpus.
    Loads JSON monographs, parses clinical sections, and produces RAG-ready chunks.
    """

    def __init__(self, data_dir: Optional[Path | str] = None):
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Corpus directory not found at: {self.data_dir}")
        self._documents: Optional[List[DrugDocument]] = None

    def __len__(self) -> int:
        return len(self.documents)

    def __iter__(self) -> Iterator[DrugDocument]:
        return iter(self.documents)

    @property
    def documents(self) -> List[DrugDocument]:
        """Lazy loads all drug documents from JSON files."""
        if self._documents is None:
            self._documents = list(self._load_all_documents())
        return self._documents

    def reload(self) -> None:
        """Force reload documents from disk."""
        self._documents = None
        _ = self.documents

    def _load_all_documents(self) -> Generator[DrugDocument, None, None]:
        """Scan and parse all .json files in the corpus directory."""
        json_files = sorted(self.data_dir.glob("*/*/*.json"))
        for fpath in json_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Extract sections
                raw_sections = data.get("sections", [])
                sections = [
                    Section(
                        key=s.get("key", ""),
                        label=s.get("label", ""),
                        number=str(s.get("number", "")),
                        title=s.get("title", ""),
                        text=s.get("text", "") or "",
                    )
                    for s in raw_sections
                ]

                # Determine folder/dossier name
                # Path format: <data_dir>/<dossier>/<sub_dossier>/<file>.json
                dossier = fpath.parent.parent.name

                doc = DrugDocument(
                    file_path=fpath,
                    dossier=dossier,
                    brand=data.get("brand", "").strip(),
                    dci=data.get("dci", "").strip(),
                    lab=data.get("lab", "").strip(),
                    source=data.get("source", "anpp"),
                    source_priority=int(data.get("source_priority", 1)),
                    doc_type=data.get("doc_type", "rcp"),
                    match_type=data.get("match_type", "exact"),
                    language=data.get("language", "fr"),
                    url=data.get("url", ""),
                    title=data.get("title", "").strip(),
                    text=data.get("text", "") or "",
                    sections=sections,
                    raw_data=data,
                )
                yield doc
            except Exception as e:
                logger.warning("Error reading %s: %s", fpath, e)

    def filter(
        self,
        dci: Optional[str] = None,
        brand: Optional[str] = None,
        doc_type: Optional[str] = None,
        dossier: Optional[str] = None,
    ) -> List[DrugDocument]:
        """Filter documents by DCI, brand name, document type (rcp/notice), or folder."""
        results = []
        dci_lower = dci.lower() if dci else None
        brand_lower = brand.lower() if brand else None
        doc_type_lower = doc_type.lower() if doc_type else None

        for doc in self.documents:
            if dci_lower and dci_lower not in doc.dci.lower():
                continue
            if brand_lower and brand_lower not in doc.brand.lower():
                continue
            if doc_type_lower and doc.doc_type.lower() != doc_type_lower:
                continue
            if dossier and doc.dossier != dossier:
                continue
            results.append(doc)
        return results

    def get_all_dcis(self) -> List[str]:
        """Return unique DCIs (International Nonproprietary Names) in corpus."""
        dcis: Set[str] = {doc.dci for doc in self.documents if doc.dci}
        return sorted(list(dcis))

    def get_all_brands(self) -> List[str]:
        """Return unique brand names in corpus."""
        brands: Set[str] = {doc.brand for doc in self.documents if doc.brand}
        return sorted(list(brands))

    def get_rag_chunks(
        self,
        min_chars: int = 50,
        max_chunk_chars: int = 1500,
        overlap_chars: int = 150,
        sections_filter: Optional[Set[str]] = None,
        doc_type: Optional[str] = None,
    ) -> List[RAGChunk]:
        """
        Generate section-aware chunks optimal for medical/pharmaceutical RAG.

        Each chunk includes:
        - Structured header prepended to the text (Drug, DCI, Lab, Section title)
        - Detailed metadata for vector DB filtering (dci, brand, lab, section_key, url, doc_type)

        If a single section exceeds max_chunk_chars, it is split into overlapping windows.
        """
        chunks: List[RAGChunk] = []

        for doc in self.documents:
            if doc_type and doc.doc_type != doc_type:
                continue

            # Process each section
            for sec in doc.sections:
                if sec.is_empty():
                    continue
                if sections_filter and sec.key not in sections_filter:
                    continue

                sec_text = sec.text.strip()
                if len(sec_text) < min_chars:
                    continue

                header = f"Médicament: {doc.brand} | DCI: {doc.dci} | Forme/Lab: {doc.lab} | Section: {sec.label or sec.title}"

                # Base metadata
                base_metadata = {
                    "brand": doc.brand,
                    "dci": doc.dci,
                    "lab": doc.lab,
                    "source": doc.source,
                    "doc_type": doc.doc_type,
                    "url": doc.url,
                    "dossier": doc.dossier,
                    "section_key": sec.key,
                    "section_number": sec.number,
                    "section_label": sec.label or sec.title,
                    "file_name": doc.file_path.name,
                }

                # If section is small enough, keep as single cohesive chunk
                if len(sec_text) <= max_chunk_chars:
                    chunk_text = f"{header}\n\n{sec_text}"
                    chunks.append(RAGChunk(text=chunk_text, metadata=dict(base_metadata)))
                else:
                    # Sliding window chunking with overlap
                    start = 0
                    part = 1
                    while start < len(sec_text):
                        end = min(start + max_chunk_chars, len(sec_text))
                        sub_text = sec_text[start:end].strip()
                        if len(sub_text) >= min_chars:
                            chunk_text = f"{header} (Partie {part})\n\n{sub_text}"
                            meta = dict(base_metadata)
                            meta["chunk_part"] = part
                            chunks.append(RAGChunk(text=chunk_text, metadata=meta))
                            part += 1
                        if end == len(sec_text):
                            break
                        start += max_chunk_chars - overlap_chars

        return chunks

    def get_manifest(self) -> List[Dict[str, str]]:
        """Read _MANIFESTE.csv if present in the data folder."""
        manifest_path = self.data_dir / "_MANIFESTE.csv"
        if not manifest_path.exists():
            return []
        with open(manifest_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            return list(reader)

    def get_resume(self) -> List[Dict[str, str]]:
        """Read _RESUME.csv if present in the data folder."""
        resume_path = self.data_dir / "_RESUME.csv"
        if not resume_path.exists():
            return []
        with open(resume_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            return list(reader)

    def export_chunks_jsonl(self, output_file: Path | str, **chunk_kwargs) -> int:
        """Export chunks to a JSONL file ready for vector DB ingestion or fine-tuning."""
        out_path = Path(output_file)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        chunks = self.get_rag_chunks(**chunk_kwargs)
        with open(out_path, "w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        return len(chunks)

