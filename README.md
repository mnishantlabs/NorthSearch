# Deep Research

**Unrestricted AI-powered research tool** that searches the entire web — including the dark web — and synthesizes findings using local uncensored LLMs.

No API keys required. No content filtering. Runs 100% on your machine.

## Features

- **Full web search** — Aggregates results from multiple engines: DuckDuckGo, Brave, Bing, and optionally SearXNG (drop-in, no API keys)
- **Dark web search** — Searches .onion hidden services via Tor (Ahmia + multiple .onion search indexes)
- **Image search** — Fetches image results from multi-engine search, with a gallery in the web UI
- **AI-powered analysis** — Uses local uncensored LLMs (Ollama) to extract and synthesize findings
- **Content verification crawler** — Fetches each candidate page and confirms it actually mentions the query before analysis (drops irrelevant pages)
- **Automatic Tor management** — Downloads, configures, and manages Tor process internally
- **Evidence ledger** — Tracks findings with confidence scores and detects contradictions
- **Rich output** — Generates both Markdown reports and structured JSON data
- **Web interface** — FastAPI + HTMX app with live progress, filters, image gallery, history with delete
- **Performer directory** — Browse a local performer database (names, videos, views), with a **face-similarity search** (upload a photo, find the most similar faces from the local photo DB using YuNet face detection + ArcFace embeddings + cosine similarity)
- **Performer crawler** — `research performers crawl` downloads performer photos + names into the local DB from the public directory
- **No content filtering** — Researches any topic without restrictions

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) installed and running
- (Optional) [Tor](https://www.torproject.org/download/tor/) for dark web search (auto-managed if missing)

### Install

```bash
git clone https://github.com/mnishantlabs/NorthSearch.git
cd NorthSearch
pip install -e .
```

Optionally enable the performer face-similarity feature (requires the ONNX face
models, ~166 MB — see **Performers** below):

```bash
pip install -e ".[performers]"
```

### Pull an uncensored model

```bash
# Best for 6GB VRAM (RTX 2060, etc.)
ollama pull dolphin3:8b

# Alternative: faster, slightly less capable
ollama pull dolphin-mistral
```

### Run (CLI)

```bash
# Basic research (clearnet only)
research "music streaming platforms"

# With dark web search
research "music platforms" --darkweb

# Image search only
research "retro cars" --images

# Choose search engines
research "quantum computing" --engines duckduckgo,bing,brave,searxng

# Disable content verification (fetch everything)
research "topic" --no-verify

# Use a specific model
research "quantum computing" --model dolphin3:8b

# Full options
research "underground markets" \
  --darkweb \
  --max-sources 30 \
  --model dolphin3:8b \
  --output-dir ./reports \
  --verbose
```

### Run (Web UI)

```bash
python run_web.py
```

Opens http://127.0.0.1:8000 with a search box, live progress streaming, image gallery, filterable results, and a history page with per-job delete.

## CLI Options

| Flag | Short | Description | Default |
|------|-------|-------------|---------|
| `--darkweb` | `-d` | Enable dark web (.onion) search | OFF |
| `--images` | `-i` | Image-only search (skip text report) | OFF |
| `--engines` | `-e` | Comma-separated: `duckduckgo,brave,bing,searxng` | ddg,brave,bing |
| `--verify` / `--no-verify` | — | Verify pages mention the query before analysis | ON |
| `--model` | `-m` | Ollama model name | `dolphin3:8b` |
| `--max-sources` | `-s` | Max sources to extract | 30 |
| `--max-sub-queries` | `-q` | Max search sub-queries | 5 |
| `--output-dir` | `-o` | Output directory | `./output` |
| `--verbose` | `-v` | Verbose logging | OFF |
| `--version` | `-V` | Show version | — |

## Performers (face similarity + directory + crawler)

The **Performers** tab (`/performers` in the web UI, or the `research performers`
CLI commands) lets you browse a local performer directory and search it by face.

### Setup

1. Install the extra dependencies:

   ```bash
   pip install -e ".[performers]"
   ```

2. Put the ONNX models in `data/performers/models/`:

   - `yunet.onnx` — [OpenCV YuNet face detector](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet)
   - `w600k_r50.onnx` — [InsightFace ArcFace embedding model](https://github.com/deepinsight/insightface/releases/tag/v0.7) (`buffalo_l`)

   The embedding index is built automatically on first face search (~1 min for
   a few hundred photos).

### Crawl to download images + names

```bash
# Download performer photos + names into data/performers/
research performers crawl --max 200 --pages 6 --gender female

# Rebuild the directory + face index afterwards is done automatically.
# To force it manually:
research performers crawl --max 200
```

### Browse + face search (CLI)

```bash
research performers browse "abella"
research performers faces photo.jpg --top-k 8
```

### Face search (web)

Open http://127.0.0.1:8000/performers, go to **Face Similarity Search**, upload a
photo, and the top matches from the local DB are returned with similarity
scores. Face matching is limited to the **local performer database** only.

## How It Works

```
User Query
    │
    ▼
┌─────────────────┐
│ 1. DECOMPOSE    │  LLM breaks query into 3-5 diverse sub-queries
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│ 2a. WEB│ │ 2b. DARK│  Multi-engine search (DDG, Brave, Bing,
│ SEARCH │ │  WEB    │  SearXNG) + .onion indexes via Tor
└───┬────┘ └───┬────┘
    └────┬─────┘
         ▼
┌─────────────────┐
│ 3. FUSION       │  Reciprocal Rank Fusion + deduplication
└────────┬────────┘
         ▼
┌─────────────────┐
│ 4. CRAWL+VERIFY │  Fetch pages, confirm they mention the query
└────────┬────────┘  (drop irrelevant), then trafilatura extracts text
         ▼
┌─────────────────┐
│ 5. ANALYZE      │  LLM extracts findings with confidence scores
└────────┬────────┘
         ▼
┌─────────────────┐
│ 6. SYNTHESIZE   │  LLM writes comprehensive report with citations
└────────┬────────┘
         ▼
┌─────────────────┐
│ 7. OUTPUT       │  Markdown report + JSON data
└─────────────────┘
```

## Project Structure

```
deep-research/
├── research/
│   ├── cli.py              # CLI entry point
│   ├── config.py           # Configuration management
│   ├── models.py           # Pydantic data models (incl. ImageResult)
│   ├── pipeline.py         # Main orchestration engine
│   ├── performers/         # Performer directory + face similarity
│   │   ├── database.py     # PerformerDatabase (browse/search/sort)
│   │   ├── faces.py        # FaceSimilarityEngine (YuNet + ArcFace + cosine)
│   │   └── crawler.py      # Photo + name downloader for the local DB
│   ├── search/
│   │   ├── engine.py       # Multi-provider search dispatcher
│   │   ├── providers/      # DuckDuckGo, Brave, Bing, SearXNG
│   │   ├── classification.py
│   │   ├── decomposer.py   # LLM query decomposition
│   │   ├── fusion.py       # Reciprocal Rank Fusion
│   │   └── darkweb.py      # Tor management + .onion search
│   ├── extraction/
│   │   ├── crawler.py      # Content verification crawler (new)
│   │   ├── extractor.py    # Trafilatura content extraction
│   │   └── html_fetcher.py # HTTP client (clearnet + Tor)
│   ├── llm/
│   │   ├── ollama_client.py # Ollama API client
│   │   └── prompts.py      # LLM prompt templates
│   └── synthesis/
│       ├── analyzer.py     # Per-source LLM analysis
│       ├── evidence.py     # Evidence ledger
│       └── reporter.py     # Report generation
├── webapp/                 # FastAPI + HTMX web interface
│   ├── server.py           # Routes (research, images, history, performers, delete)
│   ├── jobs.py             # Background job manager + persistence
│   ├── performers_store.py # Web helpers for performer DB / face search / crawl
│   ├── progress.py         # SSE event broadcast
│   ├── templates/          # Jinja2 templates (incl. performers.html)
│   └── static/             # CSS + JS (live progress, filtering, gallery)
├── run_web.py              # Launch the web UI
├── data/performers/        # Performer DB data (photos, models, xlsx) — gitignored
├── output/                 # Generated reports + history
├── pyproject.toml
└── README.md
```

## Recommended Models by GPU

| VRAM | Model | Command |
|------|-------|---------|
| 6 GB | dolphin3:8b | `ollama pull dolphin3:8b` |
| 6 GB | dolphin-mistral | `ollama pull dolphin-mistral` |
| 8 GB | qwen3-abliterated:8b | `ollama pull huihui_ai/qwen3-abliterated:8b` |
| 12 GB | qwen3-abliterated:14b | `ollama pull huihui_ai/qwen3-abliterated:14b` |
| 24 GB | qwen3-abliterated:32b | `ollama pull huihui_ai/qwen3-abliterated:32b` |
| 48 GB+ | llama3.3-abliterated:70b | `ollama pull huihui_ai/llama3.3-abliterated:70b` |

## Configuration

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `RESEARCH_MODEL` | `dolphin3:8b` | LLM model name |
| `TOR_SOCKS_PROXY` | `socks5h://127.0.0.1:9050` | Tor SOCKS proxy |
| `MAX_SOURCES` | `30` | Max sources to process |
| `MAX_SUB_QUERIES` | `5` | Max search sub-queries |
| `SEARCH_ENGINES` | `duckduckgo,brave,bing` | Active search engines |
| `SEARXNG_URL` | `https://searx.be` | Public SearXNG instance |
| `VERIFY_CONTENT` | `true` | Crawl-verify pages before analysis |
| `VERIFY_MIN_TERMS` | `1` | Min query terms a page must contain |
| `RESEARCH_HOST` | `127.0.0.1` | Web UI bind host |
| `RESEARCH_PORT` | `8000` | Web UI port |
| `PERFORMER_DATA_DIR` | `data/performers` | Performer DB location |
| `PERFORMER_TOP_K` | `8` | Max face-similarity matches |
| `PERFORMER_MIN_SIMILARITY` | `0.15` | Min cosine similarity to keep a face match |

## Tech Stack

| Component | Library | Why |
|-----------|---------|-----|
| Search | [ddgs](https://github.com/deedy5/ddgs) + Brave/Bing/SearXNG | Free, no API keys, multi-engine |
| Extraction | [trafilatura](https://github.com/adbar/trafilatura) | Best text extraction quality |
| Tor | [httpx-socks](https://github.com/lexiforest/httpx-socks) + [stem](https://github.com/torproject/stem) | SOCKS5 proxy + circuit control |
| LLM | [Ollama](https://ollama.com) | Local uncensored inference |
| CLI | [typer](https://github.com/tiangolo/typer) | Modern Python CLI |
| Rich UI | [rich](https://github.com/Textualize/rich) | Progress bars, tables, colors |
| Web | [FastAPI](https://fastapi.tiangolo.com) + HTMX + SSE | Live streaming UI |

## License

MIT
