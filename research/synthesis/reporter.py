"""Final report generation using LLM."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from research.llm.ollama_client import OllamaClient
from research.llm.prompts import (
    CONTRADICTIONS_NOTE,
    EMPTY_CONTRADICTIONS,
    SYNTHESIS_PROMPT,
    SYNTHESIS_SYSTEM,
)
from research.models import ExtractedSource, ResearchReport, ReportSection
from research.synthesis.evidence import EvidenceLedger

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Synthesizes all evidence into a final research report."""

    def __init__(self, llm: OllamaClient) -> None:
        self.llm = llm

    def generate(
        self,
        query: str,
        ledger: EvidenceLedger,
        sources: list[ExtractedSource],
        model_used: str = "",
    ) -> ResearchReport:
        """Generate a comprehensive research report."""
        logger.info(
            "Generating report from %d findings across %d sources...",
            len(ledger.findings),
            len(sources),
        )

        # Build the prompt
        findings_text = ledger.to_formatted_text()
        contradictions = ledger.get_contradictions()

        if contradictions:
            contradictions_section = CONTRADICTIONS_NOTE.format(
                contradictions="\n".join(f"- {c}" for c in contradictions[:10])
            )
        else:
            contradictions_section = EMPTY_CONTRADICTIONS

        prompt = SYNTHESIS_PROMPT.format(
            query=query,
            source_count=len(sources),
            findings_text=findings_text,
            contradictions_section=contradictions_section,
        )

        # Generate the report
        try:
            raw_report = self.llm.chat(prompt, system=SYNTHESIS_SYSTEM, temperature=0.3)
        except Exception as e:
            logger.error("Report generation failed: %s", e)
            raw_report = self._generate_fallback(query, ledger, sources)

        # Parse into sections
        sections = self._parse_sections(raw_report)

        # Count dark web sources
        darkweb_count = sum(1 for s in sources if s.source_type.value == "darkweb")

        report = ResearchReport(
            query=query,
            summary=sections[0].content if sections else "",
            sections=sections,
            findings=ledger.get_all(),
            sources=sources,
            contradictions=contradictions,
            model_used=model_used,
            total_sources=len(sources),
            darkweb_sources=darkweb_count,
        )

        return report

    def save(self, report: ResearchReport, output_dir: Path) -> tuple[Path, Path]:
        """Save the report as both Markdown and JSON.

        Also saves individual extracted sources into output_dir/sources/.

        Returns (markdown_path, json_path).
        """
        safe_name = re.sub(r'[^\w\s-]', '', report.query.lower())
        safe_name = re.sub(r'\s+', '_', safe_name)[:50]

        md_path = output_dir / f"{safe_name}_report.md"
        json_path = output_dir / f"{safe_name}_data.json"

        # Write Markdown
        md_content = self._to_markdown(report)
        md_path.write_text(md_content, encoding="utf-8")

        # Write JSON
        json_content = report.model_dump_json(indent=2)
        json_path.write_text(json_content, encoding="utf-8")

        # Save individual sources into a sources/ subfolder
        sources_dir = output_dir / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        for i, source in enumerate(report.sources, 1):
            if not source.text:
                continue
            # Sanitize a filename from title or index
            fname = re.sub(r'[^\w\s-]', '', source.title or str(i))
            fname = re.sub(r'\s+', '_', fname.strip())[:50] or str(i)
            src_rel = f"{i:02d}_{fname}.txt"
            src_path = sources_dir / src_rel
            src_path.write_text(
                f"URL: {source.url}\n"
                f"Title: {source.title}\n"
                f"Type: {source.source_type.value}\n"
                f"Quality: {source.quality_score:.2f}\n"
                f"{'=' * 60}\n\n"
                f"{source.text}",
                encoding="utf-8",
            )

        logger.info("Report saved to: %s", md_path)
        logger.info("Data saved to: %s", json_path)
        logger.info("Sources saved to: %s", sources_dir)

        return md_path, json_path

    def _to_markdown(self, report: ResearchReport) -> str:
        """Convert report to GitHub-flavored Markdown."""
        lines: list[str] = []

        lines.append(f"# Research Report: {report.query}")
        lines.append("")
        lines.append(f"*Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M')} | "
                      f"Model: {report.model_used} | "
                      f"Sources: {report.total_sources} "
                      f"({report.darkweb_sources} dark web)*")
        lines.append("")

        # Table of contents
        lines.append("## Table of Contents")
        lines.append("")
        for i, section in enumerate(report.sections):
            anchor = section.title.lower().replace(" ", "-")
            lines.append(f"{i+1}. [{section.title}](#{anchor})")
        lines.append("")

        # Sections
        for section in report.sections:
            lines.append(f"## {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")

        # Sources appendix (only if the report did not already include one)
        if not any(
            section.title.lower() in ("sources", "references", "source list")
            for section in report.sections
        ):
            lines.append("---")
            lines.append("")
            lines.append("## Sources")
            lines.append("")
            for i, source in enumerate(report.sources, 1):
                lines.append(f"[{i}] [{source.title or source.url}]({source.url}) "
                              f"*({source.source_type.value}, quality: {source.quality_score:.1f})*")
            lines.append("")

        # Contradictions
        if report.contradictions:
            lines.append("## Contradictions Found")
            lines.append("")
            for c in report.contradictions:
                lines.append(f"- {c}")
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _parse_sections(raw: str) -> list[ReportSection]:
        """Parse the raw LLM output into ReportSection objects."""
        sections: list[ReportSection] = []

        # Split on ## headings
        parts = re.split(r"^## (.+)$", raw, flags=re.MULTILINE)

        # If no sections found, treat entire output as one section
        if len(parts) < 2:
            sections.append(ReportSection(title="Report", content=raw.strip()))
            return sections

        # First part is any text before the first heading
        if parts[0].strip():
            sections.append(ReportSection(title="Executive Summary", content=parts[0].strip()))

        # Process heading/content pairs
        for i in range(1, len(parts), 2):
            title = parts[i].strip()
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if content:
                sections.append(ReportSection(title=title, content=content))

        return sections

    @staticmethod
    def _generate_fallback(
        query: str, ledger: EvidenceLedger, sources: list[ExtractedSource]
    ) -> str:
        """Generate a basic report without LLM (fallback)."""
        lines = [
            f"# Research: {query}",
            "",
            "## Key Findings",
            "",
        ]

        high_conf = ledger.get_high_confidence(0.7)
        for f in high_conf[:20]:
            lines.append(f"- {f.content} *(confidence: {f.confidence:.1f})*")

        lines.extend([
            "",
            "## All Sources",
            "",
        ])
        for i, s in enumerate(sources, 1):
            lines.append(f"{i}. [{s.title or s.url}]({s.url})")

        return "\n".join(lines)
