"""Evaluate sparse lexical, dense semantic, and hybrid Qdrant retrieval."""

from __future__ import annotations

import argparse
import json
import logging
import math
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai_api.Retrieval.chunking import DEFAULT_DATA_DIR, chunk_corpus
from ai_api.Retrieval.embedding import BGEM3Embedder
from ai_api.Retrieval.vector_store import QdrantConfig, QdrantVectorStore

try:
    from qdrant_client.models import (
        FieldCondition,
        Filter,
        Fusion,
        FusionQuery,
        MatchValue,
        Prefetch,
        SparseVector,
    )
except ImportError as exc:
    raise SystemExit(
        "qdrant-client is required. Install ai_api/requirements.txt in the active environment."
    ) from exc


BENCHMARK_PATH = PROJECT_ROOT / "evaluation" / "retrieval_benchmark.json"
MODES = ("sparse_lexical", "semantic", "hybrid")


@dataclass(frozen=True)
class SearchResult:
    chunk_id: str
    score: float
    metadata: dict[str, Any]


def relevant_grades(case: dict[str, Any]) -> dict[str, int]:
    expected = case["expected"]
    grades = {chunk_id: 2 for chunk_id in expected["chunk_ids"]}
    grades.update({chunk_id: 1 for chunk_id in expected["acceptable_chunk_ids"]})
    return grades


def recall_at_k(results: list[SearchResult], grades: dict[str, int], k: int) -> float:
    relevant = set(grades)
    if not relevant:
        return 0.0
    found = {result.chunk_id for result in results[:k]} & relevant
    return len(found) / len(relevant)


def reciprocal_rank(results: list[SearchResult], grades: dict[str, int]) -> float:
    for rank, result in enumerate(results, start=1):
        if grades.get(result.chunk_id, 0) > 0:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(results: list[SearchResult], grades: dict[str, int], k: int) -> float:
    gains = [grades.get(result.chunk_id, 0) for result in results[:k]]
    dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, start=1))
    ideal_gains = sorted(grades.values(), reverse=True)[:k]
    idcg = sum(
        gain / math.log2(rank + 1)
        for rank, gain in enumerate(ideal_gains, start=1)
    )
    return dcg / idcg if idcg else 0.0


def filter_accuracy(
    results: list[SearchResult], constraints: dict[str, Any], required: list[str]
) -> float:
    if not results:
        return 0.0
    checks = [
        result.metadata.get(field) == constraints[field]
        for result in results
        for field in required
    ]
    return sum(checks) / len(checks) if checks else 1.0


def load_benchmark(path: Path) -> dict[str, Any]:
    try:
        benchmark = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Cannot read benchmark file {path}: {exc}") from exc

    cases = benchmark.get("cases")
    if not isinstance(cases, list) or not cases:
        raise SystemExit(f"Benchmark {path} must contain a non-empty 'cases' list.")
    ids = [case.get("id") for case in cases]
    if any(not case_id for case_id in ids) or len(ids) != len(set(ids)):
        raise SystemExit("Every benchmark case must have a unique, non-empty id.")
    if not benchmark.get("k_values") or any(k < 1 for k in benchmark["k_values"]):
        raise SystemExit("'k_values' must contain positive integers.")
    return benchmark


def check_index(
    store: QdrantVectorStore,
    benchmark: dict[str, Any],
    allow_partial: bool,
) -> tuple[int, list[str]]:
    client = store.get_client()
    collection_name = store.config.collection_name
    if not client.collection_exists(collection_name):
        raise SystemExit(
            f"Qdrant collection '{collection_name}' does not exist. "
            "Index the corpus first with: python -m ai_api.Retrieval.retriever index"
        )

    corpus_ids: set[str] = set()
    corpus_metadata: dict[str, dict[str, Any]] = {}
    total_chunks = 0
    for chunk in chunk_corpus(DEFAULT_DATA_DIR):
        total_chunks += 1
        corpus_ids.add(chunk.chunk_id)
        corpus_metadata.setdefault(chunk.chunk_id, chunk.metadata)

    referenced_ids: set[str] = set()
    for case in benchmark["cases"]:
        expected = case["expected"]
        referenced_ids.update(expected["chunk_ids"])
        referenced_ids.update(expected["acceptable_chunk_ids"])

    invalid_labels = sorted(referenced_ids - corpus_ids)
    if invalid_labels:
        raise SystemExit(
            "Benchmark references chunk IDs absent from the current corpus: "
            + ", ".join(invalid_labels)
            + ". Rebuild and re-judge these labels."
        )

    for case in benchmark["cases"]:
        constraints = case["constraints"]
        for chunk_id in (
            case["expected"]["chunk_ids"] + case["expected"]["acceptable_chunk_ids"]
        ):
            metadata = corpus_metadata[chunk_id]
            mismatches = [
                field
                for field in case["expected"]["must_match_filters"]
                if metadata.get(field) != constraints.get(field)
            ]
            if mismatches:
                raise SystemExit(
                    f"{case['id']}: corpus metadata for {chunk_id} does not match "
                    f"the benchmark constraints: {', '.join(mismatches)}."
                )

    indexed_count = client.count(collection_name=collection_name, exact=True).count
    expected_count = len(corpus_ids)
    warnings = []
    if len(corpus_ids) < total_chunks:
        warnings.append(
            "The chunker emits duplicate chunk IDs. Qdrant upserts overwrite duplicate "
            "IDs, so some corpus chunks cannot coexist in the index."
        )
    if indexed_count != expected_count:
        message = (
            f"Index contains {indexed_count:,} points; current corpus produces "
            f"{expected_count:,} unique chunk IDs. Re-index the full corpus before "
            "using these benchmark scores."
        )
        if not allow_partial:
            raise SystemExit(message + " Use --allow-partial-index only for a smoke test.")
        warnings.append("PARTIAL INDEX: " + message)

    missing_gold = []
    for chunk_id in sorted(referenced_ids):
        records, _ = client.scroll(
            collection_name=collection_name,
            scroll_filter=Filter(
                must=[FieldCondition(key="chunk_id", match=MatchValue(value=chunk_id))]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if not records:
            missing_gold.append(chunk_id)
            continue
        payload = records[0].payload or {}
        expected_metadata = corpus_metadata[chunk_id]
        mismatches = [
            field
            for field in ("brand", "dci", "section_category", "source", "file_name", "dossier")
            if field in expected_metadata and payload.get(field) != expected_metadata[field]
        ]
        if mismatches:
            missing_gold.append(f"{chunk_id} (indexed metadata mismatch: {', '.join(mismatches)})")
    if missing_gold:
        raise SystemExit(
            "Expected benchmark chunks are missing or stale in Qdrant: "
            + "; ".join(missing_gold)
            + ". Re-index the full corpus."
        )

    return indexed_count, warnings


def build_query_filter(constraints: dict[str, Any]) -> Filter | None:
    conditions = [
        FieldCondition(key=field, match=MatchValue(value=value))
        for field, value in constraints.items()
        if value is not None
    ]
    return Filter(must=conditions) if conditions else None


def run_mode(
    client: Any,
    collection_name: str,
    dense_name: str,
    sparse_name: str,
    dense_vector: list[float],
    sparse_vector: dict[int, float],
    query_filter: Filter | None,
    mode: str,
    limit: int,
) -> tuple[list[SearchResult], float]:
    sparse_query = SparseVector(
        indices=list(sparse_vector.keys()),
        values=list(sparse_vector.values()),
    )

    start = time.perf_counter()
    if mode == "semantic":
        response = client.query_points(
            collection_name=collection_name,
            query=dense_vector,
            using=dense_name,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
    elif mode == "sparse_lexical":
        response = client.query_points(
            collection_name=collection_name,
            query=sparse_query,
            using=sparse_name,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
    elif mode == "hybrid":
        prefetch = [
            Prefetch(
                query=dense_vector,
                using=dense_name,
                limit=limit * 3,
                filter=query_filter,
            ),
            Prefetch(
                query=sparse_query,
                using=sparse_name,
                limit=limit * 3,
                filter=query_filter,
            ),
        ]
        response = client.query_points(
            collection_name=collection_name,
            prefetch=prefetch,
            query=FusionQuery(fusion=Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
    else:
        raise ValueError(f"Unknown retrieval mode: {mode}")

    elapsed_ms = (time.perf_counter() - start) * 1000
    results = []
    for point in response.points:
        payload = point.payload or {}
        results.append(
            SearchResult(
                chunk_id=payload.get("chunk_id", str(point.id)),
                score=float(point.score or 0.0),
                metadata=payload,
            )
        )
    return results, elapsed_ms


def evaluate(
    benchmark: dict[str, Any],
    store: QdrantVectorStore,
    embedder: BGEM3Embedder,
    limit: int,
    apply_filters: bool,
) -> dict[str, Any]:
    client = store.get_client()
    collection_name = store.config.collection_name
    dense_name = store.embedding_config.dense_vector_name
    sparse_name = store.embedding_config.sparse_vector_name
    max_k = max(benchmark["k_values"])
    result_cases = []
    metric_rows: dict[str, list[dict[str, float]]] = {mode: [] for mode in MODES}
    filter_rows: dict[str, list[float]] = {mode: [] for mode in MODES}
    negative_cases = 0

    for case in benchmark["cases"]:
        grades = relevant_grades(case)
        if not grades:
            negative_cases += 1
            result_cases.append(
                {
                    "case_id": case["id"],
                    "query_type": case["query_type"],
                    "status": "excluded_from_ranking_metrics",
                    "reason": "No positive relevance labels; abstention threshold is not configured.",
                }
            )
            continue

        encoded = embedder.encode(
            [case["query"]],
            return_dense=True,
            return_sparse=True,
        )
        dense_vector = encoded.dense[0]
        sparse_vector = (encoded.sparse or [{}])[0]
        query_filter = build_query_filter(case["constraints"]) if apply_filters else None
        case_results: dict[str, Any] = {
            "case_id": case["id"],
            "query_type": case["query_type"],
            "query": case["query"],
            "results": {},
        }

        for mode in MODES:
            results, elapsed_ms = run_mode(
                client=client,
                collection_name=collection_name,
                dense_name=dense_name,
                sparse_name=sparse_name,
                dense_vector=dense_vector,
                sparse_vector=sparse_vector,
                query_filter=query_filter,
                mode=mode,
                limit=max(limit, max_k),
            )
            mode_metrics = {
                f"recall@{k}": recall_at_k(results, grades, k)
                for k in benchmark["k_values"]
            }
            mode_metrics.update(
                {
                    f"ndcg@{k}": ndcg_at_k(results, grades, k)
                    for k in benchmark["k_values"]
                }
            )
            mode_metrics["mrr"] = reciprocal_rank(results, grades)
            required_filters = case["expected"]["must_match_filters"]
            if required_filters and not apply_filters:
                accuracy = filter_accuracy(
                    results,
                    case["constraints"],
                    required_filters,
                )
                filter_rows[mode].append(accuracy)
                mode_metrics["result_filter_accuracy"] = accuracy
            mode_metrics["latency_ms"] = elapsed_ms
            metric_rows[mode].append(mode_metrics)

            case_results["results"][mode] = {
                "metrics": mode_metrics,
                "top_results": [
                    {
                        "rank": rank,
                        "chunk_id": result.chunk_id,
                        "score": result.score,
                        "brand": result.metadata.get("brand"),
                        "dci": result.metadata.get("dci"),
                        "section_category": result.metadata.get("section_category"),
                        "source": result.metadata.get("source"),
                        "file_name": result.metadata.get("file_name"),
                    }
                    for rank, result in enumerate(results[:limit], start=1)
                ],
            }
        result_cases.append(case_results)

    summary = {}
    for mode, rows in metric_rows.items():
        if not rows:
            continue
        metric_names = rows[0].keys()
        summary[mode] = {
            metric: statistics.fmean(row[metric] for row in rows)
            for metric in metric_names
        }
        if filter_rows[mode]:
            summary[mode]["mean_result_filter_accuracy"] = statistics.fmean(
                filter_rows[mode]
            )

    return {
        "benchmark_version": benchmark["benchmark_version"],
        "corpus_version": benchmark["corpus_version"],
        "collection": collection_name,
        "embedding_model": embedder.config.model_name,
        "retrieval_modes": {
            "sparse_lexical": "BGE-M3 sparse lexical vectors (not BM25)",
            "semantic": "BGE-M3 dense vectors with cosine similarity",
            "hybrid": "BGE-M3 dense + sparse, fused with Qdrant RRF",
        },
        "filters_applied": apply_filters,
        "limit": limit,
        "k_values": benchmark["k_values"],
        "positive_cases_scored": len(result_cases) - negative_cases,
        "negative_cases_not_scored": negative_cases,
        "summary_macro_average": summary,
        "cases": result_cases,
    }


def print_summary(report: dict[str, Any]) -> None:
    print(f"Collection: {report['collection']}")
    print(f"Embedding model: {report['embedding_model']}")
    print(f"Metadata filters applied to every method: {report['filters_applied']}")
    print(
        f"Positive cases scored: {report['positive_cases_scored']}; "
        f"negative cases excluded: {report['negative_cases_not_scored']}"
    )
    print("\nMacro-averaged retrieval quality (higher is better):")
    columns = ["method", "MRR"] + [
        f"Recall@{k}" for k in report["k_values"]
    ] + [f"nDCG@{k}" for k in report["k_values"]]
    print(" | ".join(columns))
    print(" | ".join(["---"] * len(columns)))
    for mode, metrics in report["summary_macro_average"].items():
        values = [mode, f"{metrics['mrr']:.3f}"]
        values += [f"{metrics[f'recall@{k}']:.3f}" for k in report["k_values"]]
        values += [f"{metrics[f'ndcg@{k}']:.3f}" for k in report["k_values"]]
        print(" | ".join(values))
    if report["negative_cases_not_scored"]:
        print(
            "\nNegative/unsupported queries were excluded from ranking metrics. "
            "This runner does not evaluate abstention thresholds."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", type=Path, default=BENCHMARK_PATH)
    parser.add_argument("--limit", type=int, default=10, help="Results per method (default: 10)")
    parser.add_argument(
        "--apply-filters",
        action="store_true",
        help="Apply each case's metadata constraints equally to all search methods.",
    )
    parser.add_argument(
        "--allow-partial-index",
        action="store_true",
        help="Run a smoke test on an incomplete index; scores are not valid for full-corpus claims.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        help="Evaluate only this case ID (repeat the option for multiple cases).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to save the complete JSON report.",
    )
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    benchmark = load_benchmark(args.benchmark)
    if args.case_ids:
        cases_by_id = {case["id"]: case for case in benchmark["cases"]}
        unknown_ids = sorted(set(args.case_ids) - cases_by_id.keys())
        if unknown_ids:
            parser.error("unknown case ID(s): " + ", ".join(unknown_ids))
        benchmark = {
            **benchmark,
            "cases": [cases_by_id[case_id] for case_id in args.case_ids],
        }
    store = QdrantVectorStore(
        config=QdrantConfig(path=str(PROJECT_ROOT / "qdrant" / "storage"))
    )
    indexed_count, warnings = check_index(store, benchmark, args.allow_partial_index)
    print(f"Indexed points: {indexed_count:,}")
    for warning in warnings:
        print(f"WARNING: {warning}")

    embedder = BGEM3Embedder()
    print(f"Loading embedding model {embedder.config.model_name}...")
    report = evaluate(
        benchmark=benchmark,
        store=store,
        embedder=embedder,
        limit=args.limit,
        apply_filters=args.apply_filters,
    )
    print_summary(report)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"\nFull report saved to {args.output}")

    store.get_client().close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
