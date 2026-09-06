"""LLM prompt templates for each pipeline stage."""

# ---------------------------------------------------------------------------
# STAGE 1: Query Decomposition
# ---------------------------------------------------------------------------
DECOMPOSE_SYSTEM = """You are a research query planner. Your job is to take a single research topic and generate diverse search queries that will find comprehensive information across the entire web, including the dark web if applicable.

Rules:
- Generate queries covering different angles: what it is, how it works, comparisons, alternatives, new/emerging options, controversies, reviews
- Make queries specific enough to return useful results
- Include queries that might surface lesser-known or underground sources
- Never repeat the same query twice
- Use natural language that search engines understand"""

DECOMPOSE_PROMPT = """Research topic: {query}

Generate exactly {count} diverse search queries to thoroughly research this topic.
Cover these aspects: definition, alternatives, comparisons, new/emerging options, controversies/debates, user experiences/reviews.

Return ONLY a JSON array of objects, no other text:
[
  {{"query": "...", "aspect": "what it is", "priority": 1}},
  {{"query": "...", "aspect": "alternatives", "priority": 2}},
  ...
]"""

# ---------------------------------------------------------------------------
# STAGE 2: Per-Source Analysis
# ---------------------------------------------------------------------------
ANALYZE_SYSTEM = """You are a research analyst. Extract factual information, claims, data points, and opinions from web content. Be thorough and precise.

Rules:
- Extract ALL notable facts, statistics, names, dates, and claims
- Rate your confidence in each finding (0.0 = speculation, 1.0 = verified fact with clear source)
- Note any claims that seem unreliable or contradicted
- Preserve specific details: names, numbers, URLs, dates
- Do NOT summarize — extract discrete findings"""

ANALYZE_PROMPT = """Analyze this web source about: {topic}

Title: {title}
URL: {url}
Source type: {source_type}

Content:
{content}

Extract key findings as a JSON array:
[
  {{
    "content": "specific fact or claim extracted",
    "confidence": 0.8,
    "notes": "any caveats or context"
  }}
]

Return ONLY the JSON array, nothing else."""

# ---------------------------------------------------------------------------
# STAGE 3: Report Synthesis
# ---------------------------------------------------------------------------
SYNTHESIS_SYSTEM = """You are a research report writer. Synthesize multiple research findings into a comprehensive, well-structured report.

Rules:
- Organize findings by theme/topic, not by source
- Include specific details, numbers, names, and dates
- Cite sources using [number] format
- Present multiple perspectives when they exist
- Note contradictions and disagreements between sources
- Be comprehensive but concise
- Write with authority and clarity"""

SYNTHESIS_PROMPT = """Research query: {query}

Here are the consolidated findings from {source_count} sources:

{findings_text}

{contradictions_section}

Write a comprehensive research report with these sections:
1. Executive Summary (2-3 paragraphs)
2. Key Findings (organized by theme)
3. Detailed Analysis (each theme with evidence)
4. Comparisons (if applicable)
5. Emerging Trends / New Discoveries
6. Contradictions & Debates
7. Sources

Use [number] citations throughout. Write in clear, authoritative prose."""

CONTRADICTIONS_NOTE = """The following contradictions were found between sources:
{contradictions}

Address each contradiction in the report, noting which source is more credible and why."""

EMPTY_CONTRADICTIONS = ""
