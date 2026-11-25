from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SearchQuery:
    text: str
    limit: int = 5
    filter_dci: Optional[str] = None
    filter_category: Optional[str] = None
    filter_source: Optional[str] = None
    filter_brand: Optional[str] = None


@dataclass
class SearchHit:
    chunk_id: str
    score: float
    rank: int
    content: str
    header: str
    section_category: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "score": self.score,
            "rank": self.rank,
            "content": self.content,
            "header": self.header,
            "section_category": self.section_category,
            "metadata": dict(self.metadata),
        }


class BaseRetriever(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the method used """

    @abstractmethod
    def search(self, query: SearchQuery) -> List[SearchHit]:
        """Return the Ranked List after searching """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"