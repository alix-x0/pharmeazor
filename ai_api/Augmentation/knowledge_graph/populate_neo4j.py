"""Build a provenance-grounded knowledge graph from corpus chunks and store it in Neo4j."""

from __future__ import annotations

import argparse
import logging
from itertools import islice
from pathlib import Path
from typing import Iterable, Iterator, List, TypeVar

from ai_api.Augmentation.knowledge_graph.graph_builder import GraphBuilder
from ai_api.Augmentation.knowledge_graph.graph_storage import GraphStorage
from ai_api.Augmentation.knowledge_graph.graph_validator import GraphValidator
from ai_api.Augmentation.knowledge_graph.ontology import EntityType, KGEntity, KGRelation
from ai_api.Augmentation.knowledge_graph.relationship_extractor import DEFAULT_DATA_DIR

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _batches(items: Iterable[T], batch_size: int) -> Iterator[List[T]]:
    iterator = iter(items)
    while batch := list(islice(iterator, batch_size)):
        yield batch


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract a medical knowledge graph from chunked corpus data and upsert it into Neo4j."
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--dossier", help="Only include matching dossier folder, e.g. 01_paracetamol.")
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        help="Limit to a source (repeat for multiple), e.g. --source anpp.",
    )
    parser.add_argument("--max-docs", type=int, help="Limit the number of source documents, useful for a smoke run.")
    parser.add_argument("--batch-size", type=int, default=500, help="Neo4j write batch size (default: 500).")
    parser.add_argument("--dry-run", action="store_true", help="Build and validate without connecting to Neo4j.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.batch_size < 1:
        raise ValueError("--batch-size must be greater than zero")
    if args.max_docs is not None and args.max_docs < 1:
        raise ValueError("--max-docs must be greater than zero")

    builder = GraphBuilder()
    builder.build_from_chunked_corpus(
        data_dir=args.data_dir,
        dossier=args.dossier,
        sources=args.sources,
        max_docs=args.max_docs,
    )

    report = GraphValidator(builder).validate()
    report.print_summary()
    stats = builder.get_statistics()
    print(f"Chunks processed : {builder.stats.chunks_processed}")
    print(f"Documents processed : {builder.stats.documents_processed}")
    print(f"Graph stats : {stats}")

    if not report.is_valid():
        logger.error("Validation errors found; refusing to write this graph to Neo4j.")
        return 2
    if args.dry_run:
        print("Dry run complete; Neo4j was not contacted.")
        return 0

    entities: List[KGEntity] = [
        entity
        for entity_type in EntityType
        for entity in builder.get_entities_by_type(entity_type)
    ]
    relations: List[KGRelation] = builder.get_relations()
    nodes_stored = 0
    relationships_stored = 0
    relationships_skipped = 0

    with GraphStorage() as storage:
        storage.verify_connectivity()
        storage.create_constraints()

        # Upserts happen in bounded, idempotent transactions; rerunning is safe.
        for batch in _batches(entities, args.batch_size):
            summary = storage.store_graph((batch, []))
            nodes_stored += summary["nodes_stored"]
        for batch in _batches(relations, args.batch_size):
            summary = storage.store_graph(([], batch))
            relationships_stored += summary["relationships_stored"]
            relationships_skipped += summary["relationships_skipped"]

    print(
        "Neo4j upsert complete: "
        f"{nodes_stored} entities, {relationships_stored} relationships, "
        f"{relationships_skipped} relationships skipped."
    )
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
