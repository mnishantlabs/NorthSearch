"""Pydantic data models for the research pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    CLEARNET = "clearnet"
    DARKWEB = "darkweb"
    ACADEMIC = "academic"
    UNKNOWN = "unknown"


class SearchResult(BaseModel):
    """A single search result before extraction."""

    url: str
    title: str = ""
    snippet: str = ""
    source_engine: str = ""
    rank: int = 0
    source_type: SourceType = SourceType.CLEARNET


class ImageResult(BaseModel):
    """A single image search result."""

    image_url: str
    thumbnail_url: str = ""
    title: str = ""
    page_url: str = ""
    source_engine: str = ""
    source_type: SourceType = SourceType.CLEARNET
    width: int = 0
    height: int = 0


class ExtractedSource(BaseModel):
    """A fully extracted and cleaned web source."""

    url: str
    title: str = ""
    text: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    source_type: SourceType = SourceType.CLEARNET
    quality_score: float = 0.0
    extract_time: float = 0.0
    error: str | None = None


class Finding(BaseModel):
    """A single researched fact or claim extracted from a source."""

    topic: str
    content: str
    source_url: str
    source_title: str = ""
    source_type: SourceType = SourceType.CLEARNET
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    contradictions: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)


class SubQuery(BaseModel):
    """A decomposed sub-query generated from the original research query."""

    query: str
    aspect: str = ""
    priority: int = 0


class ResearchPlan(BaseModel):
    """The full research plan before execution."""

    original_query: str
    sub_queries: list[SubQuery] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class ResearchReport(BaseModel):
    """The final synthesized research report."""

    query: str
    summary: str = ""
    sections: list[ReportSection] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    sources: list[ExtractedSource] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)
    model_used: str = ""
    total_sources: int = 0
    darkweb_sources: int = 0


class ReportSection(BaseModel):
    """A section within the research report."""

    title: str
    content: str
    citations: list[int] = Field(default_factory=list)


# Fix forward reference
ResearchReport.model_rebuild()
