"""Extract the curated medication corpus and persist it to Neo4j."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence, Set

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[3]
API_DIR = PROJECT_ROOT / "ai_api"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Read ai_api/.env for this CLI while preserving explicitly exported variables.
load_dotenv(API_DIR / ".env", override=False)

from ai_api.Augmentation.knowledge_graph.graph_storage import GraphStorage, Neo4jConfig
from ai_api.Augmentation.knowledge_graph.relationship_extractor import (
    DEFAULT_DATA_DIR,
    RelationshipExtractor,
)

logger = logging.getLogger("pharmeazor.neo4j_ingest")


def _matches_filter(value: Any, allowed: Optional[Set[str]]) -> bool:
    return allowed is None or str(value or "").strip().lower() in allowed


def ingest_corpus(
    data_dir: Path,
    *,
    dossiers: Optional[Sequence[str]] = None,
    sources: Optional[Sequence[str]] = None,
    doc_types: Optional[Sequence[str]] = None,
    max_docs: Optional[int] = None,
    confidence_threshold: float = 0.7,
) -> Dict[str, Any]:
    """Ingest matching corpus documents idempotently, one transaction per file."""
    root = data_dir.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Corpus directory not found: {root}")
    if max_docs is not None and max_docs < 1:
        raise ValueError("max_docs must be at least 1")
    if not 0.0 <= confidence_threshold <= 1.0:
        raise ValueError("confidence_threshold must be between 0 and 1")

    dossier_filters = [value.lower() for value in dossiers] if dossiers else None
    source_filters = {value.lower() for value in sources} if sources else None
    doc_type_filters = {value.lower() for value in doc_types} if doc_types else None
    extractor = RelationshipExtractor(confidence_threshold=confidence_threshold)
    storage = GraphStorage(Neo4jConfig.from_env())
    counts = {
        "documents_processed": 0,
        "documents_failed": 0,
        "nodes_written": 0,
        "relationships_written": 0,
        "relationships_skipped": 0,
    }

    try:
        storage.verify_connectivity()
        storage.create_constraints()

        for path in sorted(root.glob("*/*/*.json")):
            if path.name.startswith("_"):
                continue

            dossier = path.parent.parent.name
            if dossier_filters and not any(value in dossier.lower() for value in dossier_filters):
                continue

            try:
                with path.open("r", encoding="utf-8") as source_file:
                    document = json.load(source_file)
                if not isinstance(document, dict):
                    raise ValueError("document root must be a JSON object")

                if not _matches_filter(document.get("source"), source_filters):
                    continue
                if not _matches_filter(document.get("doc_type"), doc_type_filters):
                    continue

                document = dict(document)
                document.setdefault("dossier", dossier)
                relative_doc_id = path.relative_to(root).as_posix()
                result = extractor.extract_from_document(document, doc_id=relative_doc_id)

                source = document.get("source")
                source_url = document.get("url") or document.get("source_url")
                doc_type = document.get("doc_type")
                provenance = {
                    key: value
                    for key, value in {
                        "source": source,
                        "source_url": source_url,
                        "doc_type": doc_type,
                        "dossier": document.get("dossier"),
                    }.items()
                    if value not in (None, "")
                }
                relations = [
                    replace(relation, metadata={**relation.metadata, **provenance})
                    for relation in result.relations
                ]
                enriched_result = replace(result, relations=relations)
            except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
                logger.warning("Skipping unreadable corpus document %s: %s", path, exc)
                counts["documents_failed"] += 1
                continue

            summary = storage.store_graph(enriched_result)
            counts["documents_processed"] += 1
            counts["nodes_written"] += summary["nodes_stored"]
            counts["relationships_written"] += summary["relationships_stored"]
            counts["relationships_skipped"] += summary["relationships_skipped"]
            if max_docs is not None and counts["documents_processed"] >= max_docs:
                break

        counts["database"] = storage.get_graph_statistics()
        return counts
    finally:
        storage.close()


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract the Pharmeazor corpus and store the knowledge graph in Neo4j."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--dossiers", nargs="*", help="Optional dossier-name substring filters")
    parser.add_argument("--sources", nargs="*", help="Exact source filters, e.g. anpp bdpm")
    parser.add_argument("--doc-types", nargs="*", help="Exact document type filters")
    parser.add_argument("--max-docs", type=int, help="Optional cap on matching documents")
    parser.add_argument("--confidence-threshold", type=float, default=0.7)
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = _parse_args(argv)
    try:
        result = ingest_corpus(
            args.data_dir,
            dossiers=args.dossiers,
            sources=args.sources,
            doc_types=args.doc_types,
            max_docs=args.max_docs,
            confidence_threshold=args.confidence_threshold,
        )
    except Exception as exc:
        logger.error("Neo4j corpus ingestion failed: %s", exc)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
