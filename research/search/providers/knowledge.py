"""Persistent Knowledge Base search provider."""

from __future__ import annotations

import logging
from research.models import SearchResult
from research.search.providers.base import SearchProvider
from research.storage.knowledge_index import KnowledgeIndex

logger = logging.getLogger(__name__)


class KnowledgeProvider(SearchProvider):
    name = "knowledge"

    def search(self, query: str, max_results: int) -> list[SearchResult]:
        try:
            ki = KnowledgeIndex.get_instance()
            return ki.search(query, limit=max_results)
        except Exception as e:
            logger.debug("KnowledgeProvider search error: %s", e)
            return []
