"""Main research pipeline orchestrator."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from research.config import ResearchConfig
from research.models import ResearchReport, SearchResult
from research.ui import found_urls, progress_log, section_header, subsection

logger = logging.getLogger(__name__)


class ResearchPipeline:
    """End-to-end research pipeline.

    Flow:
        Query -> Decompose -> Search -> Extract -> Analyze -> Synthesize -> Save

    Progress events: set ``on_event`` to a callable taking a dict to receive
    live progress updates (used by the web UI). The callback receives a
    reusable dict that is mutated between calls (see ``_emit``).
    """

    def __init__(self, config: ResearchConfig) -> None:
        from research.extraction.crawler import ContentVerifier
        from research.extraction.html_fetcher import HttpFetcher
        from research.llm.ollama_client import OllamaClient
        from research.search.darkweb import DarkWebSearcher
        from research.search.decomposer import QueryDecomposer
        from research.search.engine import SearchEngine
        from research.synthesis.analyzer import SourceAnalyzer
        from research.synthesis.evidence import EvidenceLedger
        from research.synthesis.reporter import ReportGenerator

        self.config = config
        self.llm = OllamaClient(config.ollama)
        self.search_engine = SearchEngine(config.search)
        self.decomposer = QueryDecomposer(self.llm)
        self.fetcher = HttpFetcher(config.extraction, config.tor)
        self.verifier = ContentVerifier(config.extraction, self.fetcher)
        self.darkweb = DarkWebSearcher(config.tor) if config.darkweb_enabled else None
        self.analyzer = SourceAnalyzer(self.llm)
        self.reporter = ReportGenerator(self.llm)
        self.ledger: EvidenceLedger | None = None
        self.on_event: Callable[[dict[str, Any]], None] | None = None
        self._event: dict[str, Any] = {}

    def _emit(self, **fields: Any) -> None:
        """Emit a progress event. Mutates a shared dict for efficiency.

        The callback must copy the dict if it retains it across calls.
        """
        self._event.clear()
        self._event.update(fields)
        if self.on_event is not None:
            try:
                self.on_event(self._event)
            except Exception:  # never let UI errors break research
                logger.debug("Error in progress event handler", exc_info=True)

    def run(self, query: str) -> ResearchReport:
        """Execute the full research pipeline."""
        # Ensure output directory exists and is prepared
        topic_dir = self._prepare_topic_dir(query)

        # ── Step 0: Check Ollama ──────────────────────────────
        section_header("Step 1: AI Analysis Engine", "Starting the local LLM")
        self._emit(type="stage", title="AI Analysis Engine", detail="Starting the local LLM")
        if not self.llm.is_available():
            raise ConnectionError(
                "Ollama is not running. Start it with: ollama serve\n"
                f"Expected at: {self.config.ollama.url}"
            )
        models = self.llm.list_models()
        if self.config.ollama.model not in models:
            available = ", ".join(models[:5]) or "(none)"
            if models:
                logger.warning(
                    "Model '%s' not found, using '%s'",
                    self.config.ollama.model,
                    models[0],
                )
                self.config.ollama.model = models[0]
                self.llm.config.model = models[0]
            else:
                raise RuntimeError(
                    "No models available in Ollama. Pull one with: ollama pull dolphin3:8b"
                )
        progress_log(f"Model ready: [bold]{self.config.ollama.model}[/bold]")
        self._emit(type="status", message=f"Model ready: {self.config.ollama.model}")

        # ── Step 1: Decompose query ───────────────────────────
        section_header(
            "Step 2: Query Planning",
            f'Breaking down "{query}" into sub-queries',
        )
        self._emit(type="stage", title="Query Planning", detail='Breaking down the query')
        sub_query_limit = self._effective_sub_queries()
        sub_queries = self.decomposer.decompose(query, sub_query_limit)
        emitted = []
        for sq in sub_queries:
            progress_log(f"[dim]{sq.aspect}[/dim] -> [bold]{sq.query}[/bold]", style="white")
            emitted.append({"query": sq.query, "aspect": sq.aspect})
        self._emit(type="plan", sub_queries=emitted)

        # ── Step 2: Search clearnet ───────────────────────────
        run_clearnet = getattr(self.config.search, "darkweb_mode", "normal") in ("normal", "all", "hybrid")
        run_darknet = getattr(self.config.search, "darkweb_mode", "normal") in ("darknet_only", "all", "hybrid", "darkweb") or bool(self.darkweb)

        results_by_query: list[list[SearchResult]] = []
        all_results: list[SearchResult] = []

        if run_clearnet:
            section_header("Step 3: Web Search", "Searching the public internet")
            self._emit(type="stage", title="Web Search", detail="Searching the public internet")
            for sq in sub_queries:
                subsection(f'Query: "{sq.query}"')
                self._emit(type="search_query", query=sq.query, status="searching")
                results = self.search_engine.search(sq.query)
                results_by_query.append(results)
                all_results.extend(results)
                progress_log(f"{len(results)} results found", style="white")
                self._emit(
                    type="search_query",
                    query=sq.query,
                    status="done",
                    count=len(results),
                    results=[
                        {"url": r.url, "title": r.title, "snippet": r.snippet[:150]}
                        for r in results
                    ],
                )

        # ── Step 2b: Search dark web ──────────────────────────
        darkweb_results: list[SearchResult] = []
        if self.darkweb and run_darknet:
            section_header("Step 3b: Dark Web Search", "Searching .onion hidden services")
            self._emit(type="stage", title="Dark Web Search", detail="Searching .onion hidden services")
            for sq in sub_queries:
                subsection(f'Dark web query: "{sq.query}"')
                dr = self.darkweb.search(sq.query, max_results=5)
                darkweb_results.extend(dr)
                results_by_query.append(dr)
                progress_log(f"{len(dr)} dark web results", style="white")
                self._emit(
                    type="darkweb_query",
                    query=sq.query,
                    count=len(dr),
                    results=[
                        {"url": r.url, "title": r.title, "snippet": r.snippet[:150]}
                        for r in dr
                    ],
                )

        # ── Step 3: Fusion ────────────────────────────────────
        section_header("Step 4: Result Fusion", "Merging and ranking all sources")
        self._emit(type="stage", title="Result Fusion", detail="Merging and ranking all sources")
        from research.search.fusion import deduplicate, reciprocal_rank_fusion

        fused = reciprocal_rank_fusion(results_by_query, k=self.config.search.fusion_k)
        fused = deduplicate(fused)

        # Split into clearweb/darkweb for display
        clear_urls = [r.url for r in fused if r.source_type.value != "darkweb"]
        dark_urls = [r.url for r in fused if r.source_type.value == "darkweb"]

        found_urls(clear_urls, max_show=10)
        if dark_urls:
            subsection("Dark web URLs")
            found_urls(dark_urls, max_show=10)

        # Emit the full fused URL list once (deduplicated) for the web UI
        self._emit(
            type="found_urls",
            count=len(fused),
            clear_count=len(clear_urls),
            dark_count=len(dark_urls),
            urls=[
                {
                    "url": r.url,
                    "title": r.title,
                    "snippet": r.snippet[:150],
                    "source_type": r.source_type.value,
                }
                for r in fused
            ],
        )

        # Save the full list of found links to a file
        self._save_links_file(topic_dir, query, fused)

        # ── Step 4: Extract content ───────────────────────────
        section_header("Step 5: Content Extraction", "Fetching and verifying pages")
        self._emit(type="stage", title="Content Extraction", detail="Fetching and verifying content")
        use_tor = self.config.darkweb_enabled
        # Crawl pages and verify they contain the query before analyzing.
        sources = self.verifier.verify_and_extract(
            fused,
            query=query,
            max_sources=self._effective_max_sources(),
            use_tor=use_tor,
            on_extracted=self._on_extracted,
        )
        progress_log(f"Extracted content from [bold]{len(sources)}[/bold] sources")

        # ── Step 5: Analyze sources ───────────────────────────
        section_header("Step 6: AI Analysis", "Extracting key findings")
        self._emit(type="stage", title="AI Analysis", detail="Extracting key findings")
        from research.synthesis.evidence import EvidenceLedger

        self.ledger = EvidenceLedger()
        findings = self.analyzer.analyze_batch(sources, topic=query, on_finding=self._on_finding)
        self.ledger.add_batch(findings)

        avg_conf = sum(f.confidence for f in findings) / max(len(findings), 1)
        progress_log(
            f"Extracted [bold]{len(findings)}[/bold] findings "
            f"(avg confidence: {avg_conf:.2f})"
        )
        if self.ledger.get_contradictions():
            progress_log(
                f"[yellow]{len(self.ledger.get_contradictions())} contradictions found[/yellow]",
                style="yellow",
            )

        # ── Step 6: Generate report ───────────────────────────
        section_header("Step 7: Report Generation", "Synthesizing findings into report")
        self._emit(type="stage", title="Report Generation", detail="Synthesizing findings into report")
        report = self.reporter.generate(
            query=query,
            ledger=self.ledger,
            sources=sources,
            model_used=self.config.ollama.model,
        )
        progress_log("Report generated")
        self._emit(
            type="report",
            summary=report.summary,
            sections=[{"title": s.title, "content": s.content} for s in report.sections],
            contradictions=report.contradictions,
        )

        # ── Step 7: Save output ───────────────────────────────
        section_header("Step 8: Saving Output", f"Saving to {topic_dir}")
        self._emit(type="stage", title="Saving Output", detail=f"Saving to {topic_dir}")
        md_path, json_path = self.reporter.save(report, topic_dir)
        progress_log(f"[bold]Report:[/bold] {md_path}")
        progress_log(f"[bold]JSON data:[/bold] {json_path}")
        progress_log(f"[bold]Found links:[/bold] {topic_dir / 'found_links.md'}")
        progress_log(f"[bold]Individual sources:[/bold] {topic_dir / 'sources'}")

        self._emit(
            type="done",
            topic_dir=str(topic_dir),
            report_path=str(md_path),
            json_path=str(json_path),
            links_path=str(topic_dir / "found_links.md"),
        )

        return report

    def _on_extracted(self, source: Any) -> None:
        """Emit a progress event when a single source is extracted."""
        self._emit(
            type="source",
            url=source.url,
            title=source.title or "",
            word_count=len(source.text or "") if not source.error else 0,
            error=source.error,
            quality=round(source.quality_score, 2),
            source_type=source.source_type.value,
        )

    def _on_finding(self, finding: Any) -> None:
        """Emit a progress event when a single finding is extracted."""
        self._emit(
            type="finding",
            topic=finding.topic,
            content=finding.content,
            confidence=round(finding.confidence, 2),
            source_url=finding.source_url,
            source_type=finding.source_type.value,
            contradictions=finding.contradictions,
        )

    def run_images(self, query: str) -> list[Any]:
        """Run an image-only search and return ImageResult list."""
        section_header("Image Search", f'Searching images for "{query}"')
        self._emit(type="stage", title="Image Search", detail=f'Searching images for "{query}"')
        images = self.search_engine.search_images(query)
        for img in images:
            self._emit(
                type="image",
                image_url=img.image_url,
                thumbnail_url=img.thumbnail_url,
                title=img.title,
                page_url=img.page_url,
                source_engine=img.source_engine,
                source_type=img.source_type.value,
            )
        self._emit(type="images_done", count=len(images))
        progress_log(f"Found [bold]{len(images)}[/bold] images across providers")
        return images

    def _effective_sub_queries(self) -> int:
        """Deep search raises the query-decomposition budget."""
        base = self.config.search.max_sub_queries
        return int(base * 2) if self.config.search.deep else base

    def _effective_max_sources(self) -> int:
        """Deep search raises the number of pages extracted."""
        base = self.config.max_sources
        return int(base * 2) if self.config.search.deep else base

    def _prepare_topic_dir(self, query: str) -> Path:
        """Create a per-topic output directory with a nice structure.

        Structure:
            output/
                <topic>/                    (sanitized query)
                    report.md               (main report)
                    data.json               (structured data)
                    found_links.md          (all URLs found)
                    sources/                (individual extracted sources)
        """
        safe_name = self._slugify(query)
        topic_dir = self.config.output_dir / safe_name
        sources_dir = topic_dir / "sources"
        sources_dir.mkdir(parents=True, exist_ok=True)
        return topic_dir

    def _save_links_file(
        self, topic_dir: Path, query: str, results: list[SearchResult]
    ) -> Path:
        """Save all found URLs to a links file."""
        links_path = topic_dir / "found_links.md"

        lines = [f"# Found Links: {query}", ""]
        lines.append(f"*Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        lines.append(f"*Total URLs found: {len(results)}*")
        lines.append("")

        current_source: str | None = None
        for i, r in enumerate(results, 1):
            src_label = (
                "darkweb"
                if r.source_type.value == "darkweb"
                else "academic"
                if r.source_type.value == "academic"
                else "web"
            )
            if src_label != current_source:
                current_source = src_label
                lines.append(f"## {src_label.capitalize()}")
                lines.append("")

            title = r.title or r.url
            lines.append(f"- [{title}]({r.url})")
            if r.snippet:
                lines.append(f"  {r.snippet[:150]}")

        links_path.write_text("\n".join(lines), encoding="utf-8")
        return links_path

    @staticmethod
    def _slugify(text: str) -> str:
        """Create a safe folder name from a query string."""
        safe = re.sub(r"[^\w\s-]", "", text.lower())
        safe = re.sub(r"\s+", "_", safe.strip())
        return safe[:60] or "research"

    def close(self) -> None:
        """Clean up resources."""
        self.fetcher.close()
        self.search_engine.close()
        self.llm.close()
        if self.darkweb:
            self.darkweb.close()

    def __enter__(self) -> "ResearchPipeline":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
