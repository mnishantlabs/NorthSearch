"""Shared URL classification helpers."""

from __future__ import annotations

from research.models import SourceType

ACADEMIC_MARKERS = [
    ".edu",
    "arxiv.org",
    "scholar.google",
    "pubmed",
    "ncbi.nlm.nih.gov",
    "ieee.org",
    "acm.org",
    "springer.com",
    "researchgate.net",
    "academia.edu",
    ".gov",
    ".mil",
]


def classify_source(url: str) -> SourceType:
    """Classify a URL into a SourceType."""
    url_lower = url.lower()
    if ".onion" in url_lower:
        return SourceType.DARKWEB
    if any(m in url_lower for m in ACADEMIC_MARKERS):
        return SourceType.ACADEMIC
    return SourceType.CLEARNET