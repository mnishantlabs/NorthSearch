"""Configuration management for Deep Research tool."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field


class OllamaConfig(BaseModel):
    """Ollama LLM connection settings."""

    url: str = Field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://localhost:11434"))
    model: str = Field(default_factory=lambda: os.getenv("RESEARCH_MODEL", "dolphin3:8b"))
    timeout: int = 120
    temperature: float = 0.3
    max_tokens: int = 4096


class TorConfig(BaseModel):
    """Tor proxy and dark web settings."""

    socks_proxy: str = Field(
        default_factory=lambda: os.getenv("TOR_SOCKS_PROXY", "socks5h://127.0.0.1:9050")
    )
    control_port: int = Field(
        default_factory=lambda: int(os.getenv("TOR_CONTROL_PORT", "9051"))
    )
    control_password: str = Field(default_factory=lambda: os.getenv("TOR_CONTROL_PASSWORD", ""))
    request_timeout: int = 60
    auto_manage: bool = True
    data_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "tor_data")

    # Windows: path to tor.exe in Expert Bundle
    # Will be auto-downloaded if not found
    tor_binary: Path | None = None


class SearchConfig(BaseModel):
    """Search engine settings."""

    max_results_per_query: int = 15
    max_sub_queries: int = Field(
        default_factory=lambda: int(os.getenv("MAX_SUB_QUERIES", "5"))
    )
    fusion_k: float = 60.0
    # Enabled search engines. Supported: duckduckgo, brave, bing, searxng
    engines: list[str] = Field(
        default_factory=lambda: [
            e.strip()
            for e in os.getenv("SEARCH_ENGINES", "duckduckgo,brave,bing").split(",")
            if e.strip()
        ]
    )
    # Public SearXNG instance to use when the "searxng" engine is enabled.
    searxng_base_url: str = Field(
        default_factory=lambda: os.getenv("SEARXNG_URL", "https://searx.be")
    )
    # Image search settings
    max_images_per_query: int = Field(
        default_factory=lambda: int(os.getenv("MAX_IMAGES_PER_QUERY", "12"))
    )
    # Domain quality tiers for scoring
    high_quality_domains: list[str] = Field(
        default_factory=lambda: [
            ".edu",
            ".gov",
            ".mil",
            "arxiv.org",
            "scholar.google.com",
            "pubmed.ncbi.nlm.nih.gov",
            "github.com",
            "stackoverflow.com",
            "wikipedia.org",
        ]
    )
    # Search mode: "normal" (all domains, default engines) or "adult"
    # (adult-content friendly engines, government/academic domains excluded).
    mode: str = Field(default_factory=lambda: os.getenv("SEARCH_MODE", "normal"))
    # Darkweb mode: "normal" (clearnet only), "darknet_only" (Tor only), or "all" (hybrid)
    darkweb_mode: str = Field(default_factory=lambda: os.getenv("DARKWEB_MODE", "normal"))
    # Deep search: research more angles and extract more sources.
    deep: bool = Field(
        default_factory=lambda: os.getenv("DEEP_SEARCH", "false").lower() == "true"
    )
    # Engines used when mode == "adult" (SEARCH_ENGINES_ADULT override).
    adult_engines: list[str] = Field(
        default_factory=lambda: [
            e.strip()
            for e in os.getenv("SEARCH_ENGINES_ADULT", "yandex,duckduckgo,bunkr").split(",")
            if e.strip()
        ]
    )
    # Domains excluded when mode == "adult" — government, military, academic,
    # medical-reference and encyclopedia sites. Each entry is a hostname or
    # suffix (e.g. "nih.gov" blocks any *.nih.gov host).
    adult_blocked_domains: list[str] = Field(
        default_factory=lambda: [
            ".gov",
            ".mil",
            ".edu",
            "ncbi.nlm.nih.gov",
            "pmc.ncbi.nlm.nih.gov",
            "medlineplus.gov",
            "nih.gov",
            "cdc.gov",
            "who.int",
            "arxiv.org",
            "scholar.google.com",
            "springer.com",
            "wikipedia.org",
            "britannica.com",
            "mayoclinic.org",
            "webmd.com",
        ]
    )


class ExtractionConfig(BaseModel):
    """Content extraction settings."""

    truncate_chars: int = Field(
        default_factory=lambda: int(os.getenv("CONTENT_TRUNCATE_CHARS", "15000"))
    )
    request_timeout: int = 30
    max_concurrent: int = 10
    # Content verification: fetch pages and confirm they mention the query
    # keywords before passing them to the LLM for analysis.
    verify_content: bool = Field(
        default_factory=lambda: os.getenv("VERIFY_CONTENT", "true").lower() == "true"
    )
    # Minimum number of query terms that must appear in a page to be kept.
    verify_min_terms: int = Field(
        default_factory=lambda: int(os.getenv("VERIFY_MIN_TERMS", "1"))
    )
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )


class PerformerConfig(BaseModel):
    """Face-similarity and performer-directory settings."""

    data_dir: Path = Field(
        default_factory=lambda: Path(os.getenv("PERFORMER_DATA_DIR", ""))
        if os.getenv("PERFORMER_DATA_DIR")
        else Path(__file__).parent.parent / "data" / "performers"
    )
    # max same-face matches returned from a face query
    top_k: int = Field(default_factory=lambda: int(os.getenv("PERFORMER_TOP_K", "8")))
    # similarity threshold (cosine) below which matches are dropped
    min_similarity: float = Field(
        default_factory=lambda: float(os.getenv("PERFORMER_MIN_SIMILARITY", "0.15"))
    )


class ResearchConfig(BaseModel):
    """Top-level research settings."""

    output_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "output")
    max_sources: int = Field(
        default_factory=lambda: int(os.getenv("MAX_SOURCES", "30"))
    )
    darkweb_enabled: bool = False
    verbose: bool = False

    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    tor: TorConfig = Field(default_factory=TorConfig)
    search: SearchConfig = Field(default_factory=SearchConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    performers: PerformerConfig = Field(default_factory=PerformerConfig)


def load_config(**overrides: object) -> ResearchConfig:
    """Load configuration with optional overrides."""
    config = ResearchConfig(**{k: v for k, v in overrides.items() if v is not None})
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.tor.data_dir.mkdir(parents=True, exist_ok=True)
    return config
