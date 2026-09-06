"""Evidence ledger - structured store of research findings."""

from __future__ import annotations

import logging
from collections import defaultdict

from research.models import Finding

logger = logging.getLogger(__name__)


class EvidenceLedger:
    """Accumulates and organizes findings from across all sources.

    Features:
    - Groups findings by topic/sub-query
    - Detects contradictions between sources
    - Tracks source diversity per claim
    """

    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self._topic_index: dict[str, list[int]] = defaultdict(list)
        self._contradictions: list[str] = []

    def add(self, finding: Finding) -> None:
        """Add a finding to the ledger."""
        idx = len(self.findings)
        self.findings.append(finding)
        self._topic_index[finding.topic].append(idx)

        # Check for contradictions with existing findings
        self._check_contradictions(finding)

    def add_batch(self, findings: list[Finding]) -> None:
        """Add multiple findings."""
        for f in findings:
            self.add(f)

    def get_by_topic(self, topic: str) -> list[Finding]:
        """Get all findings for a specific topic."""
        indices = self._topic_index.get(topic, [])
        return [self.findings[i] for i in indices]

    def get_all(self) -> list[Finding]:
        """Get all findings sorted by confidence (highest first)."""
        return sorted(self.findings, key=lambda f: f.confidence, reverse=True)

    def get_high_confidence(self, threshold: float = 0.7) -> list[Finding]:
        """Get findings above a confidence threshold."""
        return [f for f in self.findings if f.confidence >= threshold]

    def get_contradictions(self) -> list[str]:
        """Return detected contradictions."""
        return self._contradictions

    def get_source_count(self) -> int:
        """Get the number of unique sources."""
        return len({f.source_url for f in self.findings})

    def get_topic_summary(self) -> dict[str, dict]:
        """Get a summary of findings per topic."""
        summary: dict[str, dict] = {}
        for topic, indices in self._topic_index.items():
            topic_findings = [self.findings[i] for i in indices]
            sources = {f.source_url for f in topic_findings}
            avg_confidence = (
                sum(f.confidence for f in topic_findings) / len(topic_findings)
                if topic_findings
                else 0
            )
            summary[topic] = {
                "count": len(topic_findings),
                "sources": len(sources),
                "avg_confidence": round(avg_confidence, 2),
            }
        return summary

    def _check_contradictions(self, new_finding: Finding) -> None:
        """Simple contradiction detection based on topic overlap.

        Checks if a new finding contradicts existing findings on the same topic
        based on keyword-level disagreement signals.
        """
        contradiction_signals = [
            ("not", "is"),
            ("does not", "does"),
            ("cannot", "can"),
            ("false", "true"),
            ("no evidence", "evidence"),
            ("unproven", "proven"),
            ("debunked", "confirmed"),
            ("myth", "fact"),
        ]

        existing = self.get_by_topic(new_finding.topic)
        for old in existing:
            if old.source_url == new_finding.source_url:
                continue

            new_lower = new_finding.content.lower()
            old_lower = old.content.lower()

            for neg, pos in contradiction_signals:
                if (neg in new_lower and pos in old_lower) or (
                    pos in new_lower and neg in old_lower
                ):
                    # Check if they're talking about similar subjects
                    new_words = set(new_lower.split())
                    old_words = set(old_lower.split())
                    overlap = len(new_words & old_words) / max(
                        len(new_words | old_words), 1
                    )
                    if overlap > 0.3:
                        msg = (
                            f"Contradiction between sources:\n"
                            f"  [{old.source_url}] {old.content[:200]}\n"
                            f"  [{new_finding.source_url}] {new_finding.content[:200]}"
                        )
                        self._contradictions.append(msg)
                        new_finding.contradictions.append(msg)
                        old.contradictions.append(msg)
                        logger.info("Contradiction detected between sources")
                        break

    def to_formatted_text(self) -> str:
        """Format all findings as structured text for the synthesis prompt."""
        lines: list[str] = []

        for topic in sorted(self._topic_index.keys()):
            topic_findings = self.get_by_topic(topic)
            lines.append(f"\n## Topic: {topic}")
            lines.append(f"Sources: {len({f.source_url for f in topic_findings})}")

            for f in sorted(topic_findings, key=lambda x: x.confidence, reverse=True):
                conf_bar = "=" * int(f.confidence * 10) + "-" * (10 - int(f.confidence * 10))
                lines.append(f"  [{conf_bar}] {f.content}")
                lines.append(f"    Source: {f.source_url} ({f.source_type.value})")

        return "\n".join(lines)
