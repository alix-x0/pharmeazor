import unittest

from ai_api.Retrieval.chunking import DrugChunk
from ai_api.Retrieval.Search_Engine.base import SearchHit, SearchQuery
from ai_api.Retrieval.Search_Engine.Keyword_Search.bm25_retrieval import BM25Retriever


def _chunk(chunk_id: str, content: str, category: str = "other") -> DrugChunk:
    return DrugChunk(
        chunk_id=chunk_id,
        text=f"[HEADER]\n\n{content}",
        content=content,
        header="[HEADER]",
        metadata={
            "section_category": category,
            "dci": "PARACÉTAMOL",
            "brand": "DOLIPRANE",
            "source": "anpp",
        },
    )


class TestBM25Retriever(unittest.TestCase):
    def setUp(self):
        # دالة setUp تشتغل تلقائياً قبل كل اختبار لضمان بيانات نظيفة ومستقلة
        self.chunks = [
            _chunk(
                "c1",
                "Posologie du paracétamol 1000 mg chez l'adulte. Maximum 3000 mg par jour.",
                "posology",
            ),
            _chunk(
                "c2",
                "Contre-indication : insuffisance hépatocellulaire sévère.",
                "contraindications",
            ),
            _chunk(
                "c3",
                "Effets indésirables : nausées, vomissements, douleurs abdominales.",
                "adverse_effects",
            ),
        ]
        self.r = BM25Retriever()
        self.r.index(self.chunks)

    def test_name(self):
        # يتأكد أن اسم المحرك هو "bm25" كما هو متفق عليه في العقد
        self.assertEqual(self.r.name, "bm25")

    def test_search_returns_hits(self):
        # يتأكد أن البحث يرجع قائمة من كائنات SearchHit وليست فارغة
        hits = self.r.search(SearchQuery(text="paracétamol 1000 mg", limit=3))
        self.assertGreater(len(hits), 0)
        for h in hits:
            self.assertIsInstance(h, SearchHit)

    def test_exact_match_ranked_first(self):
        # يتأكد أن المقطع الأكثر تطابقاً مع الكلمات يأخذ الترتيب الأول (index 0)
        hits = self.r.search(SearchQuery(text="paracétamol 1000 mg maximum", limit=3))
        self.assertEqual(hits[0].chunk_id, "c1")

    def test_ranks_start_at_1(self):
        # يتأكد أن الترقيم rank يبدأ من 1 (1, 2, 3...) وليس من 0
        hits = self.r.search(SearchQuery(text="paracétamol", limit=3))
        for expected_rank, h in enumerate(hits, start=1):
            self.assertEqual(h.rank, expected_rank)

    def test_filter_category(self):
        # يتأكد أن الفلتر يقيّد النتائج بقسم contraindications فقط
        hits = self.r.search(
            SearchQuery(text="paracétamol", limit=5, filter_category="contraindications")
        )
        for h in hits:
            self.assertEqual(h.section_category, "contraindications")

    def test_empty_index_raises(self):
        # يتأكد أن تمرير قائمة فارغة [] إلى index يرمي ValueError
        with self.assertRaises(ValueError):
            BM25Retriever().index([])

    def test_search_before_index_raises(self):
        # يتأكد أن البحث قبل بناء الفهرس (بدون استدعاء index) يرمي RuntimeError
        with self.assertRaises(RuntimeError):
            BM25Retriever().search(SearchQuery(text="test"))


if __name__ == "__main__":
    unittest.main()