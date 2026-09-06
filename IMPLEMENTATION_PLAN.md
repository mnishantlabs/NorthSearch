# Implementation Plan

A living document tracking the development of **Deep Research** — an unrestricted AI-powered research tool.

## Phase 1: Core Infrastructure (v0.1.0) — Current

### Completed

- [x] Project scaffolding (pyproject.toml, directory structure)
- [x] Configuration management (`config.py`)
- [x] Pydantic data models (`models.py`)
- [x] Ollama LLM client (`llm/ollama_client.py`)
- [x] LLM prompt templates (`llm/prompts.py`)
- [x] Web search engine (`search/engine.py`) — ddgs wrapper
- [x] Query decomposition (`search/decomposer.py`) — LLM-powered
- [x] Reciprocal Rank Fusion (`search/fusion.py`)
- [x] Tor management (`search/darkweb.py`) — auto-download, start, stop
- [x] Dark web search via Ahmia.fi (`search/darkweb.py`)
- [x] HTTP fetcher with Tor support (`extraction/html_fetcher.py`)
- [x] Trafilatura content extraction (`extraction/extractor.py`)
- [x] Per-source LLM analysis (`synthesis/analyzer.py`)
- [x] Evidence ledger with contradiction detection (`synthesis/evidence.py`)
- [x] Report generation + Markdown/JSON output (`synthesis/reporter.py`)
- [x] Pipeline orchestrator (`pipeline.py`)
- [x] CLI interface (`cli.py`)
- [x] README.md
- [x] This implementation plan

## Phase 2: Stability & Polish (v0.2.0)

### Planned

- [ ] Unit tests for each module
- [ ] Integration tests for the full pipeline
- [ ] Rate limiting and retry logic for search/extraction
- [ ] Better error messages and graceful degradation
- [ ] `.env` file loading via `python-dotenv`
- [ ] Configurable search engines (add Brave, Google, Bing as options)
- [ ] Cache layer (avoid re-extracting same URLs across runs)
- [ ] Streaming report generation (show text as it's generated)
- [ ] Progress bar for extraction step (not just spinner)
- [ ] Handle Ollama model auto-pull (prompt to download missing model)

## Phase 3: Advanced Features (v0.3.0)

### Planned

- [ ] Multi-language support (search in non-English languages)
- [ ] Deep web crawling (follow links from extracted pages, configurable depth)
- [ ] Image and video search support
- [ ] PDF and document extraction
- [ ] Knowledge graph generation from findings
- [ ] Export to PDF, HTML, and DOCX formats
- [ ] Interactive CLI mode (ask follow-up questions)
- [ ] Parallel Ollama requests (analyze multiple sources simultaneously)
- [ ] Research session save/load (resume interrupted research)
- [ ] Comparison mode (research two topics side by side)

## Phase 4: Advanced Search (v0.4.0)

### Planned

- [ ] Tor circuit rotation (change IP between requests)
- [ ] Custom .onion site list for targeted crawling
- [ ] Ahmia API integration (not just HTML scraping)
- [ ] SecTor search engine support
- [ ] Archive.org integration (historical snapshots)
- [ ] Reddit, HackerNews, and forum search
- [ ] Academic paper search (arXiv, PubMed, Semantic Scholar)
- [ ] Patent and trademark database search
- [ ] Social media search (Twitter/X, Telegram)

## Phase 5: Production Ready (v1.0.0)

### Planned

- [ ] Web UI (Flask/FastAPI dashboard)
- [ ] REST API for programmatic access
- [ ] MCP server integration
- [ ] Docker containerization
- [ ] Scheduled research (cron-like)
- [ ] Multi-user support
- [ ] Research templates (market analysis, competitor research, etc.)
- [ ] Cost estimation (tokens used, time taken)
- [ ] Plugin system for custom extractors and analyzers

## Architecture Decisions

### Why Ollama (not cloud APIs)?
- **Privacy**: All inference runs locally, no data leaves the machine
- **Cost**: Zero API costs after initial setup
- **Uncensored**: Can use uncensored model variants (Dolphin, Abliterated Qwen, etc.)
- **Offline**: Works without internet (for the LLM portion)

### Why Tor bundled (not external)?
- **User experience**: No manual Tor setup required
- **Reliability**: Tool manages its own Tor process
- **Portability**: Works on any system without pre-installed Tor

### Why Reciprocal Rank Fusion?
- **Proven**: Standard algorithm in information retrieval literature (k=60)
- **Free**: No training data or API needed
- **Effective**: Rewards documents appearing in multiple result lists
- **Parameter-light**: Only one tuning parameter (k)

### Why Trafilatura for extraction?
- **Best quality**: Highest F1 score in academic benchmarks (0.92)
- **Fast**: 200-500 pages/sec/core
- **Rich**: Extracts text, metadata, dates, authors
- **Battle-tested**: Used by Stanford, Allen Institute, and major research tools

## Dependencies

| v0.1.0 | Purpose |
|--------|---------|
| ddgs | Web search (free, no API key) |
| trafilatura | Content extraction |
| httpx | HTTP client |
| httpx-socks | SOCKS5 proxy support |
| stem | Tor process control |
| pysocks | SOCKS protocol |
| typer | CLI framework |
| rich | Terminal UI |
| pydantic | Data validation |

## Model Strategy

### Current (v0.1.0)
- Ollama with any local model
- Recommended: `dolphin3:8b` (uncensored, fits 6GB VRAM)

### Future
- Support llama-cpp-python (no Ollama dependency)
- Support Hugging Face transformers
- Cloud LLM fallback (OpenAI, Anthropic, Gemini)
- Multi-model pipeline (fast model for extraction, slow model for synthesis)

## Contributing

This is in early development. Contributions welcome for:
1. Adding new search providers
2. Improving extraction quality
3. Better LLM prompts
4. Testing and bug reports
5. Documentation

## Changelog

### v0.1.0 (2026-09-06)
- Initial release
- Full pipeline: Decompose -> Search -> Extract -> Analyze -> Synthesize -> Report
- Clearnet search via ddgs
- Dark web search via Tor + Ahmia.fi
- Ollama integration for local uncensored LLMs
- Auto Tor management (download, start, stop)
- Evidence ledger with contradiction detection
- Markdown + JSON output
- Rich CLI with progress indicators
