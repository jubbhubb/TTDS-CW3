from abc import ABC, abstractmethod

from core.index import PositionalIndex
from core.models import Document, SearchResult


class RankingStrategy(ABC):
    """Base class for all ranking strategies."""

    @abstractmethod
    def rank(
        self,
        query_tokens: list[str],
        candidate_docs: list[Document],
        index: PositionalIndex,
    ) -> list[SearchResult]:
        ...