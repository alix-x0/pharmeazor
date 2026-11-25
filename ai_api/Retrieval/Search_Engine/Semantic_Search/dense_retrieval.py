import logging
from typing import List

from qdrant_client.models import FieldCondition, Filter, MatchValue

from ai_api.Retrieval.embedding import BGEM3Embedder, QdrantVectorStore
from ai_api.Retrieval.Search_Engine.base import BaseRetriever, SearchHit, SearchQuery

logger = logging.getLogger(__name__)


class DenseRetriever(BaseRetriever):
    def __init__(self, embedder: BGEM3Embedder, vector_store: QdrantVectorStore):
        self.embedder = embedder
        self.vector_store = vector_store

    @property
    def name(self) -> str:
        return "dense"

    def search(self, query: SearchQuery) -> List[SearchHit]:
        vector, _ = self.embedder.encode_query(query.text)

        must = []
        if query.filter_dci is not None:
            must.append(FieldCondition(key="dci", match=MatchValue(value=query.filter_dci)))
        if query.filter_brand is not None:
            must.append(FieldCondition(key="brand", match=MatchValue(value=query.filter_brand)))
        if query.filter_category is not None:
            must.append(
                FieldCondition(key="section_category", match=MatchValue(value=query.filter_category))
            )
        if query.filter_source is not None:
            must.append(FieldCondition(key="source", match=MatchValue(value=query.filter_source)))

        q_filter = Filter(must=must) if must else None

        client = self.vector_store.get_client()
        response = client.query_points(
            collection_name=self.vector_store.config.collection_name,
            query=vector,
            using=self.vector_store.embedding_config.dense_vector_name,
            limit=query.limit,
            query_filter=q_filter,
        )

        hits = []
        for rank, point in enumerate(response.points, start=1):
            payload = point.payload or {}
            hits.append(
                SearchHit(
                    payload.get("chunk_id", str(point.id)),
                    float(point.score or 0.0),
                    rank,
                    payload.get("content", ""),
                    payload.get("header", ""),
                    payload.get("section_category", "other"),
                    {
                        "source": payload.get("source"),
                        "brand": payload.get("brand"),
                        "dci": payload.get("dci"),
                    },
                )
            )

        return hits