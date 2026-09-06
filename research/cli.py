"""CLI entry point for Deep Research tool."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from research import __version__
from research.config import load_config
from research.pipeline import ResearchPipeline

app = typer.Typer(
    name="research",
    help="Deep Research - Unrestricted AI-powered research tool.",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"Deep Research v{__version__}")
        raise typer.Exit()


@app.command()
def main(
    query: str = typer.Argument(..., help="Research topic or question"),
    darkweb: bool = typer.Option(
        False, "--darkweb", "-d", help="Enable dark web (.onion) search"
    ),
    images: bool = typer.Option(
        False, "--images", "-i", help="Search images (skip text report)"
    ),
    engines: str = typer.Option(
        None, "--engines", "-e",
        help="Comma-separated search engines: duckduckgo,brave,bing,searxng",
    ),
    verify: bool = typer.Option(
        True, "--verify/--no-verify", help="Verify pages contain the query before analysis"
    ),
    model: str = typer.Option(
        None, "--model", "-m", help="Ollama model to use (default: dolphin3:8b)"
    ),
    max_sources: int = typer.Option(
        None, "--max-sources", "-s", help="Max sources to extract (default: 30)"
    ),
    max_sub_queries: int = typer.Option(
        None, "--max-sub-queries", "-q", help="Max sub-queries to generate (default: 5)"
    ),
    output_dir: str = typer.Option(
        None, "--output-dir", "-o", help="Output directory (default: ./output)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
    version: bool = typer.Option(
        False, "--version", "-V", help="Show version and exit",
        callback=version_callback,
    ),
) -> None:
    """Deep Research - Search the entire web and synthesize findings with AI."""

    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )
    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Load config
    config = load_config(
        darkweb_enabled=darkweb,
        verbose=verbose,
        max_sources=max_sources,
        output_dir=Path(output_dir) if output_dir else None,
    )

    if model:
        config.ollama.model = model
    if max_sub_queries:
        config.search.max_sub_queries = max_sub_queries
    if engines:
        config.search.engines = [e.strip() for e in engines.split(",") if e.strip()]
    config.extraction.verify_content = verify

    # Banner
    console.print(
        Panel(
            f"[bold cyan]Deep Research[/bold cyan] v{__version__}\n"
            f"Query: [bold]{query}[/bold]\n"
            f"Dark web: {'[green]ON[/green]' if darkweb else '[dim]OFF[/dim]'}\n"
            f"Mode: {'[blue]images[/blue]' if images else '[green]text[/green]'}\n"
            f"Engines: {', '.join(config.search.engines)}",
            title="Starting Research",
            border_style="cyan",
        )
    )

    # Check Ollama availability
    from research.llm.ollama_client import OllamaClient

    llm = OllamaClient(config.ollama)
    if not llm.is_available():
        console.print(
            f"\n[red bold]ERROR:[/red bold] Cannot connect to Ollama at {config.ollama.url}\n\n"
            "To install Ollama:\n"
            "  1. Visit https://ollama.com/download\n"
            "  2. Download and install for Windows\n"
            "  3. Run: ollama serve\n"
            "  4. Pull a model: ollama pull dolphin3:8b\n"
        )
        raise typer.Exit(1)

    models = llm.list_models()
    if config.ollama.model not in models:
        console.print(
            f"\n[yellow]Model '{config.ollama.model}' not found.[/yellow]\n"
            f"Available models: {', '.join(models) or '(none)'}\n\n"
            f"Pull it with: ollama pull {config.ollama.model}"
        )
        if models:
            console.print(f"Using first available model: {models[0]}")
            config.ollama.model = models[0]
        else:
            console.print("[red]No models available. Pull one with: ollama pull dolphin3:8b[/red]")
            raise typer.Exit(1)
    llm.close()

    # Run pipeline
    try:
        with ResearchPipeline(config) as pipeline:
            if images:
                results = pipeline.run_images(query)
                table = Table(title="Image Search Complete", border_style="green")
                table.add_column("Engine", style="cyan")
                table.add_column("Title")
                table.add_column("Image URL")
                for img in results[:40]:
                    table.add_row(img.source_engine, img.title[:40] or "-", img.image_url)
                console.print(table)
                console.print(f"\n[bold green]{len(results)} images found.[/bold green]\n")
                raise typer.Exit(0)
            report = pipeline.run(query)
    except KeyboardInterrupt:
        console.print("\n[yellow]Research cancelled by user.[/yellow]")
        raise typer.Exit(130)
    except Exception as e:
        if images:
            raise
        console.print(f"\n[red]Research failed: {e}[/red]")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)

    # Display summary
    console.print()
    table = Table(title="Research Complete", border_style="green")
    table.add_column("Metric", style="cyan")
    table.add_column("Value")
    table.add_row("Sources analyzed", str(report.total_sources))
    table.add_row("Dark web sources", str(report.darkweb_sources))
    table.add_row("Findings extracted", str(len(report.findings)))
    table.add_row("Contradictions", str(len(report.contradictions)))
    table.add_row("Model used", report.model_used)
    console.print(table)

    console.print(
        f"\n[bold green]Report saved to:[/bold green] {config.output_dir}/\n"
    )


performer_app = typer.Typer(
    name="performers",
    help="Performer directory: face-similarity search, browse, and crawl.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode="rich",
)
app.add_typer(performer_app, name="performers")


@performer_app.command("crawl")
def performers_crawl(
    max_performers: int = typer.Option(
        100, "--max", "-m", help="Max performers to download"
    ),
    pages: int = typer.Option(6, "--pages", "-p", help="Directory pages to scan"),
    gender: str = typer.Option(
        "female", "--gender", "-g", help="gender=female|male|m2f|f2m"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose logging"),
) -> None:
    """Download performer photos + names into the local DB."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)
    config = load_config()
    from research.performers.crawler import PerformerCrawler

    crawler = PerformerCrawler(
        config.performers.data_dir,
        gender=gender,
        max_performers=max_performers,
        pages=pages,
    )
    try:
        result = crawler.run()
    finally:
        crawler.close()
    console.print(f"[bold green]Collected:[/bold green] {result['collected']}")
    console.print(f"[bold]Skipped:[/bold] {result['skipped']}")
    if result["performers"]:
        names = [p["name"] for p in result["performers"][:20]]
        console.print("Sample:", ", ".join(names))
        # rebuild database + face index with new photos
        from research.performers.database import build_performer_database
        from research.performers.faces import FaceSimilarityEngine

        db = build_performer_database(force=True)
        db.save()
        FaceSimilarityEngine(db).build_index(force=True)
        console.print(f"[bold green]Local DB now has {db.count()} performers.[/bold green]")


@performer_app.command("faces")
def performers_faces(
    photo: str = typer.Argument(..., help="Path to the input face photo"),
    top_k: int = typer.Option(8, "--top-k", "-k", help="Number of matches to return"),
    force_index: bool = typer.Option(False, "--force-index", help="Rebuild embedding index"),
) -> None:
    """Find the most similar performer faces for a photograph."""
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    from research.performers.database import build_performer_database
    from research.performers.faces import FaceSimilarityEngine

    db = build_performer_database()
    engine = FaceSimilarityEngine(db)
    if force_index or engine.requires_build():
        engine.build_index(force=force_index)
    results = engine.search(Path(photo), top_k=top_k)
    if not results:
        console.print(
            "[red]No faces matched. Try a clearer head-on photo, or rebuild the index.[/red]"
        )
        raise typer.Exit(1)

    table = Table(title="Similar Performer Faces", border_style="cyan")
    table.add_column("Similarity", style="green", justify="right")
    table.add_column("Name", style="bold white")
    table.add_column("Videos", justify="right")
    table.add_column("Views", justify="right")
    table.add_column("Photo")
    for r in results:
        table.add_row(
            f"{r['similarity']:.3f}",
            r["name"],
            str(r.get("videos", 0)),
            str(r.get("views", 0)),
            r.get("photo") or "-",
        )
    console.print(table)


@performer_app.command("browse")
def performers_browse(
    query: str = typer.Argument("", help="Name substring filter"),
    gender: str = typer.Option(None, "--gender", "-g", help="gender filter (female/male)"),
    sort_by: str = typer.Option("views", "--sort", "-s", help="views|videos|name"),
    limit: int = typer.Option(50, "--limit", "-l", help="Rows to show"),
) -> None:
    """Browse the local performer directory."""
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    from research.performers.database import build_performer_database

    db = build_performer_database()
    rows = db.search(query=query, gender=gender, sort_by=sort_by, limit=limit)
    table = Table(title=f"Performers (matching '{query or '*'}')", border_style="cyan")
    table.add_column("Name")
    table.add_column("Videos", justify="right")
    table.add_column("Views", justify="right")
    table.add_column("Photo", justify="right")
    for r in rows:
        table.add_row(r.name, str(r.videos), f"{r.views:,}", "yes" if r.photo else "")
    console.print(table)
    console.print(f"[bold]{db.count()}[/bold] performers total.")


if __name__ == "__main__":
    app()
