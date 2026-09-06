"""Content verification crawler.

After search + fusion, this module fetches each candidate page and confirms
it actually mentions the research query (or a minimum number of query
terms).  Pages that fail verification are dropped before they reach the
LLM analysis step, saving time and improving output quality.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from research.config import ExtractionConfig
from research.extraction.html_fetcher import HttpFetcher
from research.models import ExtractedSource, SearchResult, SourceType

logger = logging.getLogger(__name__)


class ContentVerifier:
    """Fetches and verifies pages, keeping only content-relevant ones."""

    def __init__(
        self,
        config: ExtractionConfig,
        fetcher: HttpFetcher,
    ) -> None:
        self.config = config
        self.fetcher = fetcher

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def verify_and_extract(
        self,
        results: list[SearchResult],
        query: str,
        max_sources: int = 30,
        use_tor: bool = False,
        on_extracted: Callable[[Any], None] | None = None,
    ) -> list[ExtractedSource]:
        """Fetch, verify, then extract content from *results*.

        1. Fetch HTML for each URL (clearnet or Tor).
        2. Confirm the page text contains the query / enough query terms.
        3. Run trafilatura extraction on verified pages.
        4. Return verified, extracted sources (up to *max_sources*).

        Pages that fail verification are silently skipped.  If the
        ``verify_content`` flag is disabled in config, every page is
        kept without verification (backwards-compatible with the
        original pipeline).
        """
        if not self.config.verify_content:
            # Original path: just extract everything, no verification
            from research.extraction.extractor import ContentExtractor

            extractor = ContentExtractor(self.config, self.fetcher)
            return extractor.extract_from_search_results(
                results,
                max_sources=max_sources,
                use_tor=use_tor,
                on_extracted=on_extracted,
            )

        import time

        import trafilatura

        query_terms = self._extract_query_terms(query)
        sources: list[ExtractedSource] = []
        attempted = 0
        total = min(len(results), max_sources + len(results) // 3)  # try a few extra to compensate

        for result in results[:total]:
            if len(sources) >= max_sources:
                break

            attempted += 1
            needs_tor = (
                use_tor
                or result.source_type == SourceType.DARKWEB
                or ".onion" in result.url
            )

            # Step 1 — fetch HTML
            html = self.fetcher.fetch(result.url, use_tor=needs_tor)
            if not html:
                continue

            # Step 2 — quick keyword verification on raw text
            plain = self._strip_tags(html)
            match_count = sum(1 for term in query_terms if term in plain)
            if match_count < self.config.verify_min_terms:
                logger.debug(
                    "Verification failed: %s (%d/%d terms)",
                    result.url,
                    match_count,
                    self.config.verify_min_terms,
                )
                continue

            # Step 3 — trafilatura extraction
            start = time.time()
            text = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
                favor_precision=False,
                favor_recall=True,
                output_format="txt",
            )

            if not text or len(text.strip()) < 100:
                continue

            if len(text) > self.config.truncate_chars:
                text = text[: self.config.truncate_chars] + "\n...[truncated]"

            elapsed = time.time() - start

            source = ExtractedSource(
                url=result.url,
                title=result.title or "",
                text=text,
                source_type=result.source_type,
                quality_score=self._quality_score(result, text),
                extract_time=elapsed,
            )

            if on_extracted is not None:
                on_extracted(source)
            sources.append(source)

        logger.info(
            "Crawler verified %d/%d pages (%d kept)",
            attempted,
            min(len(results), total),
            len(sources),
        )
        return sources

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    @staticmethod
    def _strip_tags(html: str) -> str:
        """Remove HTML tags and return lowercase plain text."""
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.lower()

    @staticmethod
    def _extract_query_terms(query: str) -> list[str]:
        """Split query into lowercase words, ignoring very short tokens."""
        stop = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to",
            "for", "of", "is", "it", "as", "by", "with", "from",
        }
        return [
            w.lower()
            for w in re.findall(r"\w{3,}", query.lower())
            if w.lower() not in stop
        ]

    @staticmethod
    def _quality_score(result: SearchResult, text: str) -> float:
        score = 0.5
        url_lower = result.url.lower()
        for domain in [".edu", ".gov", ".mil", "arxiv.org", "github.com", "wikipedia.org"]:
            if domain in url_lower:
                score += 0.2
                break
        wc = len(text.split())
        if wc > 1000:
            score += 0.1
        if wc > 3000:
            score += 0.1
        if wc < 200:
            score -= 0.1
        return min(max(score, 0.0), 1.0)