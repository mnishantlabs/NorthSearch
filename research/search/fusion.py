"""Reciprocal Rank Fusion for merging search results."""

from __future__ import annotations

import logging
from collections import defaultdict

from research.config import SearchConfig
from research.models import SearchResult

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    results_list: list[list[SearchResult]],
    k: float = 60.0,
) -> list[SearchResult]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion.

    RRF formula: score(d) = sum(1 / (k + rank_i(d))) for each list i.
    Documents appearing in more lists score higher.

    Args:
        results_list: List of ranked result lists (one per sub-query).
        k: Smoothing constant (default 60, standard in literature).

    Returns:
        Merged and deduplicated results sorted by RRF score.
    """
    url_scores: dict[str, float] = defaultdict(float)
    url_best: dict[str, SearchResult] = {}

    for results in results_list:
        for rank, result in enumerate(results, start=1):
            url = result.url.rstrip("/")
            rrf_score = 1.0 / (k + rank)
            url_scores[url] += rrf_score

            # Keep the result with the best rank (first occurrence)
            if url not in url_best or result.rank < url_best[url].rank:
                url_best[url] = result

    # Sort by fused score descending
    sorted_urls = sorted(url_scores.keys(), key=lambda u: url_scores[u], reverse=True)

    fused_results: list[SearchResult] = []
    for url in sorted_urls:
        result = url_best[url].model_copy()
        fused_results.append(result)

    logger.info(
        "RRF fusion: %d unique URLs from %d lists",
        len(fused_results),
        len(results_list),
    )

    return fused_results


def deduplicate(results: list[SearchResult]) -> list[SearchResult]:
    """Remove duplicate URLs (case-insensitive, trailing-slash-insensitive)."""
    seen: set[str] = set()
    unique: list[SearchResult] = []
    for r in results:
        key = r.url.rstrip("/").lower()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def rank_by_quality(
    results: list[SearchResult],
    high_quality_domains: list[str] | None = None,
) -> list[SearchResult]:
    """Boost ranking for high-quality domains (.edu, .gov, etc.)."""
    if not high_quality_domains:
        return results

    def quality_bonus(r: SearchResult) -> float:
        url_lower = r.url.lower()
        for domain in high_quality_domains:
            if domain in url_lower:
                return 0.5
        return 0.0

    return sorted(results, key=lambda r: quality_bonus(r), reverse=True)
