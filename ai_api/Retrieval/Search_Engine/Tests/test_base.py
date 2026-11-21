"""
Tests for base.py — SearchQuery, SearchHit, BaseRetriever.
"""

import unittest

from ai_api.Retrieval.Search_Engine.base import (
    SearchQuery,
    SearchHit,
    BaseRetriever,
)


class TestSearchQuery(unittest.TestCase):
    def test_search_query_defaults(self):
        q = SearchQuery(text="x")
        self.assertEqual(q.text, "x")
        self.assertEqual(q.limit, 5)
        self.assertIsNone(q.filter_dci)
        self.assertIsNone(q.filter_category)
        self.assertIsNone(q.filter_source)
        self.assertIsNone(q.filter_brand)


class TestSearchHit(unittest.TestCase):
    def test_search_hit_to_dict(self):
        hit = SearchHit(
            chunk_id="c1",
            score=0.95,
            rank=1,
            content="sample content",
            header="sample header",
            section_category="general",
        )
        d = hit.to_dict()

        self.assertEqual(d["chunk_id"], "c1")
        self.assertEqual(d["score"], 0.95)
        self.assertEqual(d["rank"], 1)
        self.assertEqual(d["content"], "sample content")
        self.assertEqual(d["header"], "sample header")
        self.assertEqual(d["section_category"], "general")
        self.assertEqual(d["metadata"], {})

        for key in (
            "chunk_id",
            "score",
            "rank",
            "content",
            "header",
            "section_category",
            "metadata",
        ):
            self.assertIn(key, d)

    def test_search_hit_metadata_default(self):
        hit1 = SearchHit(
            chunk_id="c1",
            score=0.8,
            rank=1,
            content="text 1",
            header="h1",
            section_category="cat1",
        )
        hit2 = SearchHit(
            chunk_id="c2",
            score=0.7,
            rank=2,
            content="text 2",
            header="h2",
            section_category="cat2",
        )

        hit1.metadata["x"] = 1
        self.assertNotIn("x", hit2.metadata)


class TestBaseRetriever(unittest.TestCase):
    def test_base_retriever_is_abstract(self):
        with self.assertRaises(TypeError):
            BaseRetriever()


if __name__ == "__main__":
    unittest.main()