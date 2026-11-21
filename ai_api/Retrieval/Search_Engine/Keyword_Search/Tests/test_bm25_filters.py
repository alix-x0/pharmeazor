import unittest

from ai_api.Retrieval.chunking import DrugChunk
from ai_api.Retrieval.Search_Engine.base import SearchQuery
from ai_api.Retrieval.Search_Engine.Keyword_Search.bm25_retrieval import BM25Retriever


class _OrderedBackend:
    def __init__(self, chunks: list[DrugChunk]):
        self.chunk_ids = list(range(len(chunks)))
        self.scores = [float(len(chunks) - index) for index in self.chunk_ids]
        self.last_k: int | None = None

    def retrieve(self, _query_tokens, k: int):
        self.last_k = k
        return [self.chunk_ids[:k]], [self.scores[:k]]


def _chunk(chunk_id: str, metadata: dict[str, str] | None) -> DrugChunk:
    return DrugChunk(
        chunk_id=chunk_id,
        text=f"[{chunk_id}]\n\nShared search text",
        content="Shared search text",
        header=f"[{chunk_id}]",
        metadata=metadata or {},
    )


class TestBM25Filters(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            _chunk(
                "paracetamol-posology",
                {
                    "dci": "PARACETAMOL",
                    "section_category": "posology",
                    "source": "anpp",
                    "brand": "DOLIPRANE",
                },
            ),
            _chunk(
                "paracetamol-contraindications",
                {
                    "dci": "PARACETAMOL",
                    "section_category": "contraindications",
                    "source": "bdpm",
                    "brand": "DOLIPRANE",
                },
            ),
            _chunk(
                "ibuprofen-posology",
                {
                    "dci": "IBUPROFEN",
                    "section_category": "posology",
                    "source": "anpp",
                    "brand": "NUROFEN",
                },
            ),
            _chunk(
                "ibuprofen-warnings",
                {
                    "dci": "IBUPROFEN",
                    "section_category": "warnings",
                    "source": "pharmnet",
                    "brand": "ADVIL",
                },
            ),
            _chunk(
                "aspirin-posology",
                {
                    "dci": "ASPIRIN",
                    "section_category": "posology",
                    "source": "bdpm",
                    "brand": "ASPIRINE",
                },
            ),
            _chunk("missing-metadata", None),
        ]
        self.retriever = BM25Retriever()
        self.retriever.index(self.chunks)
        self.backend = _OrderedBackend(self.chunks)
        self.retriever._retriever = self.backend

    def _search(self, **filters: str) -> list:
        return self.retriever.search(SearchQuery(text="shared", limit=10, **filters))

    def test_each_metadata_filter_returns_only_matching_chunks(self):
        cases = (
            ("filter_dci", "PARACETAMOL", ["paracetamol-posology", "paracetamol-contraindications"]),
            ("filter_category", "posology", ["paracetamol-posology", "ibuprofen-posology", "aspirin-posology"]),
            ("filter_source", "anpp", ["paracetamol-posology", "ibuprofen-posology"]),
            ("filter_brand", "DOLIPRANE", ["paracetamol-posology", "paracetamol-contraindications"]),
        )

        for field, value, expected_ids in cases:
            with self.subTest(filter=field):
                hits = self._search(**{field: value})
                self.assertEqual([hit.chunk_id for hit in hits], expected_ids)

    def test_all_filters_are_combined(self):
        hits = self._search(
            filter_dci="IBUPROFEN",
            filter_category="warnings",
            filter_source="pharmnet",
            filter_brand="ADVIL",
        )

        self.assertEqual([hit.chunk_id for hit in hits], ["ibuprofen-warnings"])

    def test_nonmatching_combination_returns_no_hits(self):
        hits = self._search(filter_dci="PARACETAMOL", filter_source="pharmnet")

        self.assertEqual(hits, [])

    def test_filter_excludes_chunks_with_missing_metadata(self):
        hits = self._search(filter_category="posology")

        self.assertNotIn("missing-metadata", [hit.chunk_id for hit in hits])

    def test_unfiltered_hit_maps_metadata_and_uses_defaults(self):
        hits = self._search()
        hit = hits[-1]

        self.assertEqual(hit.chunk_id, "missing-metadata")
        self.assertEqual(hit.section_category, "other")
        self.assertEqual(hit.metadata, {"source": None, "brand": None, "dci": None})

    def test_filtered_results_keep_relevance_order_and_rerank_contiguously(self):
        hits = self.retriever.search(
            SearchQuery(text="shared", limit=2, filter_category="posology")
        )

        self.assertEqual(
            [(hit.chunk_id, hit.rank) for hit in hits],
            [("paracetamol-posology", 1), ("ibuprofen-posology", 2)],
        )

    def test_search_respects_limit(self):
        hits = self.retriever.search(SearchQuery(text="shared", limit=3))

        self.assertEqual(len(hits), 3)
        self.assertEqual([hit.rank for hit in hits], [1, 2, 3])

    def test_filter_search_oversamples_up_to_index_size(self):
        self.retriever.search(
            SearchQuery(text="shared", limit=2, filter_category="posology")
        )

        self.assertEqual(self.backend.last_k, len(self.chunks))

    def test_unfiltered_search_requests_only_the_requested_limit(self):
        self.retriever.search(SearchQuery(text="shared", limit=2))

        self.assertEqual(self.backend.last_k, 2)

    def test_search_preserves_scores_as_floats(self):
        hits = self.retriever.search(SearchQuery(text="shared", limit=1))

        self.assertEqual(hits[0].score, float(len(self.chunks)))
        self.assertIsInstance(hits[0].score, float)

    def test_empty_backend_results_return_empty_list(self):
        self.backend.chunk_ids = []
        self.backend.scores = []

        self.assertEqual(self.retriever.search(SearchQuery(text="shared")), [])


if __name__ == "__main__":
    unittest.main()
