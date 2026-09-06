"""Rich terminal UI helpers for better visual output."""

from __future__ import annotations

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.rule import Rule

console = Console()


def section_header(title: str, subtitle: str = "") -> None:
    """Print a colored section header."""
    console.print()
    lines = [Text(f"  {title}", style="bold cyan")]
    if subtitle:
        lines.append(Text(f"  {subtitle}", style="dim"))
    console.print(Panel(Group(*lines), border_style="cyan"))


def found_urls(urls: list[str], max_show: int = 10) -> None:
    """Display found URLs in the terminal with numbering.

    Args:
        urls: List of URL strings to display.
        max_show: Maximum number to show. 'None'/'0' means show all.
    """
    if not urls:
        console.print("  [yellow]No URLs found[/yellow]")
        return

    shown = urls if not max_show else urls[:max_show]
    total = len(urls)

    table = Table(
        title=f"Found {total} URL{'s' if total != 1 else ''}",
        border_style="green",
        title_style="bold green",
        show_header=True,
    )
    table.add_column("#", style="cyan", width=4)
    table.add_column("URL", style="white")
    table.add_column("Source", style="yellow", width=12)

    for i, url in enumerate(shown, 1):
        source = "darkweb" if ".onion" in url else "web"
        table.add_row(str(i), url, source)

    console.print(table)

    if total > len(shown):
        console.print(f"  [dim]... and {total - len(shown)} more[/dim]")
    console.print()


def subsection(title: str, description: str = "") -> None:
    """Print a small subsection label."""
    console.print(Rule(f"[bold cyan]{title}[/bold cyan]", style="cyan"))
    if description:
        console.print(f"  [dim]{description}[/dim]")


def progress_log(message: str, style: str = "green") -> None:
    """Print a progress message with a checkmark."""
    console.print(f"  [bold {style}][OK][/bold {style}] {message}")
