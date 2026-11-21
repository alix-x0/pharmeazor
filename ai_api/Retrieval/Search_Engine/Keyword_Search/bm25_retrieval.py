import logging
from typing import List

from ai_api.Retrieval.chunking import DrugChunk
from ai_api.Retrieval.Search_Engine.base import SearchQuery, SearchHit, BaseRetriever

try:
    import bm25s
    _BM25S_AVAILABLE = True 
except ImportError:
    bm25s = None
    _BM25S_AVAILABLE = False

logger= logging.getLogger(__name__)

class BM25Retriever(BaseRetriever):
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        if _BM25S_AVAILABLE == False:
            raise ImportError('Import BM25 Error')
        self.k1 = k1
        self.b = b
        self._retriever = None
        self._chunks = []
        
    @property
    def name(self)->str:
        return 'bm25'

    def index(self, chunks:list[DrugChunk]) -> None:
        if not chunks:
            raise ValueError('Chunks list Empty')
        self._chunks = list(chunks)
        texts = [c.content for c in self._chunks]
        corpus_tokens = bm25s.tokenize(texts, stopwords = 'fr', stemmer = None, show_progress = False)
        self._retriever = bm25s.BM25(k1= self.k1, b= self.b)
        self._retriever.index(corpus_tokens)
        logger.info("Indexed %d chunks", len(self._chunks))
        pass

    def search(self, query : SearchQuery)->list[SearchHit]:
        if self._retriever == None:
            raise RuntimeError('There is no indexed data')
        query_tokens = bm25s.tokenize([query.text], stopwords = 'fr', stemmer= None, show_progress = False)
        fetch_k = (query.limit * 5) if self._has_filters(query) else query.limit
        fetch_k = min(fetch_k, len(self._chunks))
        results, scores = self._retriever.retrieve(query_tokens, k= fetch_k)

        hits =[]
        seen_chunk_idx = set()
        for idx, score in zip(results[0],scores[0]):
            chunk = self._chunks[int(idx)]
            if chunk.chunk_id in seen_chunk_idx:
                continue

            if not self._passes_filters(chunk, query):
                continue
            seen_chunk_idx.add(chunk.chunk_id)

            md = chunk.metadata or  {}  
            hits.append(SearchHit(
                chunk.chunk_id,
                float(score),
                len(hits) + 1,
                chunk.content,
                chunk.header,
                md.get('section_category', 'other'),
                {
                    'source': md.get('source'),
                    'brand': md.get('brand'),
                    'dci': md.get('dci')
                },
                ))
            if len(hits) >= query.limit:
                break

        return hits

    def _has_filters(self, query: SearchQuery) -> bool:
        return any([
            query.filter_dci is not None,
            query.filter_category is not None,
            query.filter_source is not None,
            query.filter_brand is not None,
        ])

    def _passes_filters(self, chunk: DrugChunk, query: SearchQuery) -> bool:
            md = chunk.metadata or {}

            if query.filter_dci is not None and md.get("dci") != query.filter_dci:
                return False
            if (
                query.filter_category is not None
                and md.get("section_category") != query.filter_category
            ):
                return False
            if query.filter_source is not None and md.get("source") != query.filter_source:
                return False
            if query.filter_brand is not None and md.get("brand") != query.filter_brand:
                return False

            return True
        