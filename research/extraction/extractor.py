"""Content extraction using trafilatura."""

from __future__ import annotations

import logging
import time
from typing import Callable

import trafilatura

from research.config import ExtractionConfig
from research.extraction.html_fetcher import HttpFetcher
from research.models import ExtractedSource, SearchResult, SourceType

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extracts clean text from web pages using trafilatura."""

    def __init__(
        self,
        config: ExtractionConfig,
        fetcher: HttpFetcher,
    ) -> None:
        self.config = config
        self.fetcher = fetcher

    def extract_from_search_results(
        self,
        results: list[SearchResult],
        max_sources: int = 30,
        use_tor: bool = False,
        on_extracted: Callable[[ExtractedSource], None] | None = None,
    ) -> list[ExtractedSource]:
        """Extract content from a list of search results.

        Args:
            results: Search results to extract from.
            max_sources: Maximum number of sources to process.
            use_tor: Whether to route requests through Tor.
            on_extracted: Optional callback invoked after each source is
                extracted (including failures).
        """
        sources: list[ExtractedSource] = []
        total = min(len(results), max_sources)

        for i, result in enumerate(results[:total]):
            logger.info("Extracting [%d/%d]: %s", i + 1, total, result.url)

            # Determine if this URL needs Tor
            needs_tor = use_tor or result.source_type == SourceType.DARKWEB or ".onion" in result.url

            source = self._extract_single(result, use_tor=needs_tor)
            if on_extracted is not None and source is not None:
                on_extracted(source)
            if source and not source.error:
                sources.append(source)

        logger.info("Extracted %d/%d sources successfully", len(sources), total)
        return sources

    def _extract_single(self, result: SearchResult, use_tor: bool = False) -> ExtractedSource | None:
        """Extract content from a single URL."""
        start = time.time()

        # Fetch HTML
        html = self.fetcher.fetch(result.url, use_tor=use_tor)
        if not html:
            return ExtractedSource(
                url=result.url,
                title=result.title,
                source_type=result.source_type,
                error="Failed to fetch URL",
            )

        # Extract main text with trafilatura
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
            return ExtractedSource(
                url=result.url,
                title=result.title,
                source_type=result.source_type,
                error="Insufficient content extracted",
            )

        # Truncate to context budget
        if len(text) > self.config.truncate_chars:
            text = text[: self.config.truncate_chars] + "\n...[truncated]"

        # Extract metadata
        metadata = trafilatura.extract(
            html,
            output_format="json",
            include_comments=False,
        )

        elapsed = time.time() - start

        # Calculate quality score
        quality_score = self._score_quality(result, text)

        return ExtractedSource(
            url=result.url,
            title=result.title or self._extract_title(html) or "",
            text=text,
            metadata=metadata if isinstance(metadata, dict) else {},
            source_type=result.source_type,
            quality_score=quality_score,
            extract_time=elapsed,
        )

    def _score_quality(self, result: SearchResult, text: str) -> float:
        """Score a source's quality based on heuristics."""
        score = 0.5  # base

        url_lower = result.url.lower()

        # Boost for high-quality domains
        for domain in [".edu", ".gov", ".mil", "arxiv.org", "github.com", "wikipedia.org"]:
            if domain in url_lower:
                score += 0.2
                break

        # Boost for longer, more detailed content
        word_count = len(text.split())
        if word_count > 1000:
            score += 0.1
        if word_count > 3000:
            score += 0.1

        # Penalize very short content
        if word_count < 200:
            score -= 0.1

        return min(max(score, 0.0), 1.0)

    @staticmethod
    def _extract_title(html: str) -> str:
        """Extract <title> tag from HTML."""
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            return title_tag.get_text(strip=True) if title_tag else ""
        except Exception:
            return ""
