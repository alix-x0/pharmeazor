import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from qdrant_client.models import FieldCondition, Filter, MatchValue

from ai_api.Retrieval.Search_Engine.base import SearchHit, SearchQuery
from ai_api.Retrieval.Search_Engine.Semantic_Search.dense_retrieval import DenseRetriever


class TestDenseRetriever(unittest.TestCase):
    def setUp(self):
        self.embedder = MagicMock()
        self.embedder.encode_query.return_value = ([0.1, 0.2, 0.3], {7: 1.0})
        self.client = MagicMock()
        self.client.query_points.return_value.points = []
        self.vector_store = MagicMock()
        self.vector_store.config.collection_name = "test-drugs"
        self.vector_store.embedding_config.dense_vector_name = "dense_test"
        self.vector_store.get_client.return_value = self.client
        self.retriever = DenseRetriever(self.embedder, self.vector_store)

    def _search_filter(self) -> Filter | None:
        return self.client.query_points.call_args.kwargs["query_filter"]

    def _expected_condition(self, key: str, value: str) -> FieldCondition:
        return FieldCondition(key=key, match=MatchValue(value=value))

    def test_name(self):
        self.assertEqual(self.retriever.name, "dense")

    def test_search_encodes_text_and_queries_configured_dense_collection(self):
        query = SearchQuery(text="paracetamol", limit=3)

        self.retriever.search(query)

        self.embedder.encode_query.assert_called_once_with("paracetamol")
        self.client.query_points.assert_called_once_with(
            collection_name="test-drugs",
            query=[0.1, 0.2, 0.3],
            using="dense_test",
            limit=3,
            query_filter=None,
        )
        self.vector_store.get_client.assert_called_once_with()

    def test_unfiltered_query_does_not_create_a_filter(self):
        self.retriever.search(SearchQuery(text="test"))

        self.assertIsNone(self._search_filter())

    def test_each_metadata_filter_creates_expected_condition(self):
        cases = (
            ("filter_dci", "PARACETAMOL", "dci"),
            ("filter_brand", "DOLIPRANE", "brand"),
            ("filter_category", "posology", "section_category"),
            ("filter_source", "anpp", "source"),
        )

        for field, value, payload_key in cases:
            with self.subTest(filter=field):
                self.client.reset_mock()
                self.client.query_points.return_value.points = []
                query = SearchQuery(text="drug", **{field: value})

                self.retriever.search(query)

                self.assertEqual(
                    self._search_filter(),
                    Filter(must=[self._expected_condition(payload_key, value)]),
                )

    def test_all_metadata_filters_are_combined_as_must_conditions(self):
        self.retriever.search(
            SearchQuery(
                text="drug",
                filter_dci="PARACETAMOL",
                filter_brand="DOLIPRANE",
                filter_category="posology",
                filter_source="anpp",
            )
        )

        self.assertEqual(
            self._search_filter(),
            Filter(
                must=[
                    self._expected_condition("dci", "PARACETAMOL"),
                    self._expected_condition("brand", "DOLIPRANE"),
                    self._expected_condition("section_category", "posology"),
                    self._expected_condition("source", "anpp"),
                ]
            ),
        )

    def test_results_map_payload_and_keep_backend_order(self):
        self.client.query_points.return_value.points = [
            SimpleNamespace(
                id="qdrant-1",
                score=0.91,
                payload={
                    "chunk_id": "chunk-1",
                    "content": "first content",
                    "header": "first header",
                    "section_category": "posology",
                    "source": "anpp",
                    "brand": "DOLIPRANE",
                    "dci": "PARACETAMOL",
                },
            ),
            SimpleNamespace(
                id="qdrant-2",
                score=0.72,
                payload={
                    "chunk_id": "chunk-2",
                    "content": "second content",
                    "header": "second header",
                    "section_category": "warnings",
                },
            ),
        ]

        hits = self.retriever.search(SearchQuery(text="drug"))

        self.assertEqual(hits, [
            SearchHit(
                chunk_id="chunk-1",
                score=0.91,
                rank=1,
                content="first content",
                header="first header",
                section_category="posology",
                metadata={
                    "source": "anpp",
                    "brand": "DOLIPRANE",
                    "dci": "PARACETAMOL",
                },
            ),
            SearchHit(
                chunk_id="chunk-2",
                score=0.72,
                rank=2,
                content="second content",
                header="second header",
                section_category="warnings",
                metadata={"source": None, "brand": None, "dci": None},
            ),
        ])
        self.assertTrue(all(isinstance(hit, SearchHit) for hit in hits))

    def test_missing_payload_uses_point_id_and_default_fields(self):
        self.client.query_points.return_value.points = [
            SimpleNamespace(id=42, score=0.5, payload=None)
        ]

        hits = self.retriever.search(SearchQuery(text="drug"))

        self.assertEqual(
            hits,
            [
                SearchHit(
                    chunk_id="42",
                    score=0.5,
                    rank=1,
                    content="",
                    header="",
                    section_category="other",
                    metadata={"source": None, "brand": None, "dci": None},
                )
            ],
        )

    def test_missing_chunk_id_falls_back_to_point_id(self):
        self.client.query_points.return_value.points = [
            SimpleNamespace(id="point-id", score=0.5, payload={})
        ]

        hits = self.retriever.search(SearchQuery(text="drug"))

        self.assertEqual(hits[0].chunk_id, "point-id")

    def test_missing_score_defaults_to_zero(self):
        self.client.query_points.return_value.points = [
            SimpleNamespace(id="point-id", score=None, payload={})
        ]

        hits = self.retriever.search(SearchQuery(text="drug"))

        self.assertEqual(hits[0].score, 0.0)
        self.assertIsInstance(hits[0].score, float)

    def test_empty_qdrant_response_returns_empty_list(self):
        self.client.query_points.return_value.points = []

        self.assertEqual(self.retriever.search(SearchQuery(text="drug")), [])


if __name__ == "__main__":
    unittest.main()
