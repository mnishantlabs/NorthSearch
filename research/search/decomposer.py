"""LLM-powered query decomposition."""

from __future__ import annotations

import json
import logging

from research.llm.ollama_client import OllamaClient
from research.llm.prompts import DECOMPOSE_PROMPT, DECOMPOSE_SYSTEM
from research.models import SubQuery

logger = logging.getLogger(__name__)


class QueryDecomposer:
    """Breaks a research query into diverse sub-queries using LLM."""

    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm

    def decompose(self, query: str, count: int = 5) -> list[SubQuery]:
        """Decompose a query into `count` diverse sub-queries."""
        logger.info("Decomposing query into %d sub-queries...", count)

        prompt = DECOMPOSE_PROMPT.format(query=query, count=count)
        raw = self.llm.chat(prompt, system=DECOMPOSE_SYSTEM, temperature=0.5)

        sub_queries = self._parse_response(raw, count)

        # Always include the original query as the first entry
        if not any(sq.query.lower() == query.lower() for sq in sub_queries):
            sub_queries.insert(
                0, SubQuery(query=query, aspect="original query", priority=0)
            )

        logger.info("Generated %d sub-queries:", len(sub_queries))
        for sq in sub_queries:
            logger.info("  [%d] %s (%s)", sq.priority, sq.query, sq.aspect)

        return sub_queries

    @staticmethod
    def _parse_response(raw: str, expected_count: int) -> list[SubQuery]:
        """Parse the LLM's JSON response into SubQuery objects."""
        text = raw.strip()

        # Try to extract the JSON array. The model may return either:
        #   [{"query": ...}, ...]                      (bare array)
        #   {"queries": [{"query": ...}, ...]}        (wrapped object)
        #   "Here are the queries: [...]"              (text + array)
        start = text.find("[")
        end = text.rfind("]") + 1
        if start == -1 or end <= 0:
            logger.warning("No JSON array found in decompose response")
            return []

        try:
            data = json.loads(text[start:end])
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse decompose JSON: %s", e)
            return []

        # If it's a dict (wrapped), try to find the list inside
        items: list[object] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for value in data.values():
                if isinstance(value, list):
                    items = value
                    break

        sub_queries: list[SubQuery] = []
        for item in items[:expected_count]:
            if isinstance(item, dict) and "query" in item:
                sub_queries.append(
                    SubQuery(
                        query=item["query"],
                        aspect=item.get("aspect", ""),
                        priority=item.get("priority", len(sub_queries) + 1),
                    )
                )

        return sub_queries
