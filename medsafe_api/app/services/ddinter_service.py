"""
DDInter Service

Loads every ddinter_downloads_code_*.csv file into memory and builds two indexes:
  1. interaction_map  - (drug_a_lower, drug_b_lower) -> InteractionRecord (both orderings stored)
  2. drug_index       - drug_lower -> DrugInfo

Also loads all_drugs.csv for drug metadata (Product Type, Route, Dosage Form).
Indexes are built once at startup and are read-only afterwards.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from thefuzz import process as fuzz_process

from app.core.config import settings

logger = logging.getLogger(__name__)


class DrugInfo:
    __slots__ = ("name", "ddinter_id")

    def __init__(self, name: str, ddinter_id: str):
        self.name = name
        self.ddinter_id = ddinter_id


class InteractionRecord:
    __slots__ = ("drug_a", "drug_b", "ddinter_id_a", "ddinter_id_b", "level")

    def __init__(
        self,
        drug_a: str,
        drug_b: str,
        ddinter_id_a: str,
        ddinter_id_b: str,
        level: str,
    ):
        self.drug_a = drug_a
        self.drug_b = drug_b
        self.ddinter_id_a = ddinter_id_a
        self.ddinter_id_b = ddinter_id_b
        self.level = level  # raw: Major | Moderate | Minor | Unknown


class DDInterService:
    def __init__(self) -> None:
        self._interaction_map: Dict[Tuple[str, str], InteractionRecord] = {}
        self._drug_index: Dict[str, DrugInfo] = {}
        self._drug_names_lower: List[str] = []
        self._drug_metadata_map: Dict[str, dict] = {}
        self._loaded = False

    def load(self) -> None:
        """Parse all CSV files and build in-memory indexes. Called once at startup."""
        data_dir: Path = settings.DATA_DIR
        csv_files = sorted(data_dir.glob(settings.DDINTER_CSV_GLOB))

        if not csv_files:
            logger.warning(
                "No DDInter CSV files found in %s matching '%s'. "
                "Copy the downloaded CSVs into that directory.",
                data_dir,
                settings.DDINTER_CSV_GLOB,
            )
        else:
            logger.info("Loading %d DDInter CSV file(s).", len(csv_files))

        for csv_path in csv_files:
            self._parse_csv(csv_path)

        self._drug_names_lower = sorted(self._drug_index.keys())

        self._parse_all_drugs_csv(data_dir / "all_drugs.csv")

        logger.info(
            "DDInter loaded - %d unique drugs | %d unique interaction pairs | %d metadata entries",
            len(self._drug_index),
            len(self._interaction_map) // 2,
            len(self._drug_metadata_map),
        )
        self._loaded = True

    @property
    def drug_count(self) -> int:
        return len(self._drug_index)

    @property
    def interaction_count(self) -> int:
        """Number of unique (unordered) pairs."""
        return len(self._interaction_map) // 2

    def lookup(self, drug_a_lower: str, drug_b_lower: str) -> Optional[InteractionRecord]:
        """Return the InteractionRecord for a pair, or None if not in DB."""
        return self._interaction_map.get((drug_a_lower, drug_b_lower))

    def resolve_drug(self, query: str) -> Optional[DrugInfo]:
        """Exact case-insensitive lookup of a drug name."""
        return self._drug_index.get(query.strip().lower())

    def get_drug_metadata(self, drug_name: str) -> Optional[dict]:
        """Retrieve metadata (product type, route, etc.) from all_drugs.csv."""
        return self._drug_metadata_map.get(drug_name.strip().lower())

    def fuzzy_search(self, query: str, limit: int = 10) -> List[Tuple[str, str, int]]:
        """
        Return up to `limit` drug names with fuzzy match scores.
        Used internally for drug name resolution fallback.
        Returns: [(original_name, ddinter_id, score), ...]
        """
        query_lower = query.strip().lower()
        hits = fuzz_process.extractBests(
            query_lower,
            self._drug_names_lower,
            score_cutoff=settings.FUZZY_THRESHOLD,
            limit=limit,
        )
        results = []
        for lower_name, score in hits:
            info = self._drug_index[lower_name]
            results.append((info.name, info.ddinter_id, score))
        return results

    def _parse_csv(self, path: Path) -> None:
        """Parse one DDInter CSV into the two indexes."""
        try:
            with path.open(newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    self._ingest_row(row)
        except Exception as exc:
            logger.error("Failed to parse %s: %s", path.name, exc)

    def _ingest_row(self, row: dict) -> None:
        id_a = row.get("DDInterID_A", "").strip()
        name_a = row.get("Drug_A", "").strip()
        id_b = row.get("DDInterID_B", "").strip()
        name_b = row.get("Drug_B", "").strip()
        level = row.get("Level", "").strip()

        if not (id_a and name_a and id_b and name_b and level):
            return

        lower_a = name_a.lower()
        lower_b = name_b.lower()

        if lower_a not in self._drug_index:
            self._drug_index[lower_a] = DrugInfo(name=name_a, ddinter_id=id_a)
        if lower_b not in self._drug_index:
            self._drug_index[lower_b] = DrugInfo(name=name_b, ddinter_id=id_b)

        record = InteractionRecord(
            drug_a=name_a,
            drug_b=name_b,
            ddinter_id_a=id_a,
            ddinter_id_b=id_b,
            level=level,
        )
        self._interaction_map[(lower_a, lower_b)] = record
        self._interaction_map[(lower_b, lower_a)] = record

    def _parse_all_drugs_csv(self, path: Path) -> None:
        """Parse all_drugs.csv to populate metadata map."""
        if not path.exists():
            logger.warning("Metadata file %s not found. Explanations will lack drug type context.", path.name)
            return

        try:
            with path.open(newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    generic = row.get("Generic Name", "").strip().lower()
                    brand = row.get("Brand Name", "").strip().lower()

                    meta = {
                        "product_type": row.get("Product Type", "").strip(),
                        "route": row.get("Route", "").strip(),
                        "dosage_form": row.get("Dosage Form", "").strip(),
                    }

                    if generic:
                        self._drug_metadata_map[generic] = meta
                    if brand:
                        self._drug_metadata_map[brand] = meta
        except Exception as exc:
            logger.error("Failed to parse metadata from %s: %s", path.name, exc)


ddinter_service = DDInterService()
