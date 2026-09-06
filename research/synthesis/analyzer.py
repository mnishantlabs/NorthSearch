"""Per-source analysis using LLM."""

from __future__ import annotations

import json
import logging
from typing import Callable

from research.llm.ollama_client import OllamaClient
from research.llm.prompts import ANALYZE_PROMPT, ANALYZE_SYSTEM
from research.models import ExtractedSource, Finding

logger = logging.getLogger(__name__)


class SourceAnalyzer:
    """Uses LLM to extract structured findings from each source."""

    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm

    def analyze(self, source: ExtractedSource, topic: str) -> list[Finding]:
        """Analyze a single source and extract findings."""
        if not source.text or source.error:
            return []

        prompt = ANALYZE_PROMPT.format(
            topic=topic,
            title=source.title,
            url=source.url,
            source_type=source.source_type.value,
            content=source.text[:8000],  # Limit content sent to LLM
        )

        try:
            raw = self.llm.chat(prompt, system=ANALYZE_SYSTEM, temperature=0.2)
            return self._parse_findings(raw, source, topic)
        except Exception as e:
            logger.warning("Analysis failed for %s: %s", source.url, e)
            return []

    def analyze_batch(
        self,
        sources: list[ExtractedSource],
        topic: str,
        on_finding: Callable[[Finding], None] | None = None,
    ) -> list[Finding]:
        """Analyze multiple sources and return all findings.

        Args:
            sources: Sources to analyze.
            topic: The research topic/query.
            on_finding: Optional callback invoked for each extracted finding.
        """
        all_findings: list[Finding] = []

        for i, source in enumerate(sources):
            logger.info("Analyzing [%d/%d]: %s", i + 1, len(sources), source.url)
            findings = self.analyze(source, topic)
            if on_finding is not None:
                for finding in findings:
                    on_finding(finding)
            all_findings.extend(findings)
            logger.info("  Extracted %d findings", len(findings))

        return all_findings

    def _parse_findings(
        self, raw: str, source: ExtractedSource, topic: str
    ) -> list[Finding]:
        """Parse LLM response into Finding objects."""
        text = raw.strip()
        start = text.find("[")
        end = text.rfind("]") + 1

        if start == -1 or end <= 0:
            logger.warning("No JSON array found in analysis response for %s", source.url)
            return []

        try:
            data = json.loads(text[start:end])
        except json.JSONDecodeError:
            logger.warning("Failed to parse analysis JSON for %s", source.url)
            return []

        # Handle both bare array and wrapped object formats
        items: list[object] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for value in data.values():
                if isinstance(value, list):
                    items = value
                    break

        findings: list[Finding] = []
        for item in items:
            if isinstance(item, dict) and "content" in item:
                findings.append(
                    Finding(
                        topic=topic,
                        content=item["content"],
                        source_url=source.url,
                        source_title=source.title,
                        source_type=source.source_type,
                        confidence=float(item.get("confidence", 0.5)),
                    )
                )

        return findings
