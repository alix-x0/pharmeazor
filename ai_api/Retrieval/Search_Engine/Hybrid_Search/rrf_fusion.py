from typing import Dict, List   
from dataclasses import replace

from ai_api.Retrieval.Search_Engine.base import BaseRetriever, SearchHit, SearchQuery

class RRFFusion(BaseRetriever):
    def __init__(self, retrievers : list[BaseRetriever], k: int = 60):
        if len(retrievers) < 2:
            raise ValueError("Need at least 2 retrievers for RRF fusion")
        self.retrievers = retrievers
        self.k = k

    @property
    def name(self)-> str:
        return 'hybrid_rrf'

    def search(self, query: SearchQuery) -> list[SearchHit]:
        longerlimitQuery = replace(query , limit= query.limit * 3)

        fused :Dict[str, float] = {}
        data : Dict[str, SearchHit] = {}

        for retriever in self.retrievers:
            for hit in retriever.search(longerlimitQuery):
                fused[hit.chunk_id] = fused.get(hit.chunk_id, 0.0) + 1.0 / (self.k + hit.rank)
                if hit.chunk_id not in data:
                    data[hit.chunk_id]= hit

        sorted_fused = sorted(fused, key= lambda cid: fused[cid], reverse= True)
        hits: List[SearchHit] = []
        
        for rank, cid in enumerate(sorted_fused[: query.limit], start=1):
            original = data[cid]
            hits.append(
                SearchHit(
                    chunk_id=original.chunk_id,
                    score=fused[cid],
                    rank=rank,
                    content=original.content,
                    header=original.header,
                    section_category=original.section_category,
                    metadata=original.metadata,
                )
            )

        return hits

            
    