"""Persistent Knowledge Base & Crawl Index using SQLite FTS5 for continuous search memory."""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from research.models import SearchResult

logger = logging.getLogger(__name__)

DB_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DB_DIR / "knowledge_base.db"


class KnowledgeIndex:
    """Manages full-text search indexing of all searched, crawled, and discovered web content."""

    _instance: KnowledgeIndex | None = None
    _lock = threading.Lock()

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    @classmethod
    def get_instance(cls) -> KnowledgeIndex:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self.db_path), timeout=15)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            self._local.conn = conn
        return self._local.conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE,
                    title TEXT,
                    snippet TEXT,
                    query TEXT,
                    source_engine TEXT,
                    source_type TEXT,
                    hit_count INTEGER DEFAULT 1,
                    created_at REAL,
                    updated_at REAL
                );
            """)

            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                    title,
                    snippet,
                    query,
                    url,
                    content="knowledge_items",
                    content_rowid="id"
                );
            """)

            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge_items BEGIN
                    INSERT INTO knowledge_fts(rowid, title, snippet, query, url)
                    VALUES (new.id, new.title, new.snippet, new.query, new.url);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge_items BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, snippet, query, url)
                    VALUES("delete", old.id, old.title, old.snippet, old.query, old.url);
                END;
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS knowledge_au AFTER UPDATE ON knowledge_items BEGIN
                    INSERT INTO knowledge_fts(knowledge_fts, rowid, title, snippet, query, url)
                    VALUES("delete", old.id, old.title, old.snippet, old.query, old.url);
                    INSERT INTO knowledge_fts(rowid, title, snippet, query, url)
                    VALUES (new.id, new.title, new.snippet, new.query, new.url);
                END;
            """)

    def index_result(self, result: SearchResult, query: str = "") -> bool:
        """Indexes a single search result into persistent memory."""
        if not result.url or len(result.url) < 5:
            return False

        now = time.time()
        conn = self._get_conn()
        try:
            with conn:
                conn.execute("""
                    INSERT INTO knowledge_items (url, title, snippet, query, source_engine, source_type, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(url) DO UPDATE SET
                        title = COALESCE(NULLIF(excluded.title, ""), knowledge_items.title),
                        snippet = CASE WHEN length(excluded.snippet) > length(knowledge_items.snippet) THEN excluded.snippet ELSE knowledge_items.snippet END,
                        query = knowledge_items.query || ", " || excluded.query,
                        hit_count = knowledge_items.hit_count + 1,
                        updated_at = excluded.updated_at;
                """, (
                    result.url,
                    result.title or "",
                    result.snippet or "",
                    query,
                    result.source_engine or "web",
                    result.source_type or "clearnet",
                    now,
                    now,
                ))
            return True
        except Exception as e:
            logger.debug("Failed to index result %s: %s", result.url, e)
            return False

    def index_results(self, results: list[SearchResult], query: str = "") -> int:
        """Batch index search results into persistent memory."""
        count = 0
        for r in results:
            if self.index_result(r, query=query):
                count += 1
        return count

    def index_crawled_page(self, url: str, title: str, content: str, query: str = "", source: str = "scraper") -> bool:
        """Indexes an extracted webpage with full content snippet."""
        sr = SearchResult(
            url=url,
            title=title or url,
            snippet=content[:800] if content else "",
            source_engine=source,
            rank=1,
            source_type="crawled_page",
        )
        return self.index_result(sr, query=query)

    def search(self, query: str, limit: int = 15) -> list[SearchResult]:
        """Queries the persistent knowledge base via full-text search."""
        q = query.strip()
        if not q:
            return []

        conn = self._get_conn()
        results: list[SearchResult] = []

        clean_q = "".join(c if c.isalnum() or c.isspace() else " " for c in q).strip()
        if not clean_q:
            clean_q = q

        terms = [f"\"{t}\"*" for t in clean_q.split() if t]
        match_expr = " AND ".join(terms) if terms else clean_q

        try:
            cur = conn.execute("""
                SELECT k.url, k.title, k.snippet, k.source_engine, k.source_type, k.hit_count, k.updated_at
                FROM knowledge_fts f
                JOIN knowledge_items k ON f.rowid = k.id
                WHERE knowledge_fts MATCH ?
                ORDER BY rank
                LIMIT ?;
            """, (match_expr, limit))

            for i, row in enumerate(cur.fetchall()):
                results.append(
                    SearchResult(
                        url=row["url"],
                        title=row["title"],
                        snippet=row["snippet"],
                        source_engine=f"Knowledge Base ({row["source_engine"]})",
                        rank=i + 1,
                        source_type=row["source_type"],
                    )
                )
        except Exception:
            try:
                cur = conn.execute("""
                    SELECT url, title, snippet, source_engine, source_type, hit_count, updated_at
                    FROM knowledge_items
                    WHERE title LIKE ? OR snippet LIKE ? OR query LIKE ?
                    ORDER BY hit_count DESC, updated_at DESC
                    LIMIT ?;
                """, (f"%{q}%", f"%{q}%", f"%{q}%", limit))

                for i, row in enumerate(cur.fetchall()):
                    results.append(
                        SearchResult(
                            url=row["url"],
                            title=row["title"],
                            snippet=row["snippet"],
                            source_engine=f"Knowledge Base ({row["source_engine"]})",
                            rank=i + 1,
                            source_type=row["source_type"],
                        )
                    )
            except Exception as e:
                logger.debug("Knowledge base search error: %s", e)

        return results

    def stats(self) -> dict[str, Any]:
        """Returns statistics on total indexed items, sources, and queries."""
        conn = self._get_conn()
        try:
            cur = conn.execute("SELECT COUNT(*), COUNT(DISTINCT query) FROM knowledge_items;")
            row = cur.fetchone()
            total_items = row[0] if row else 0
            distinct_queries = row[1] if row else 0

            cur_recent = conn.execute("""
                SELECT url, title, snippet, source_engine, updated_at
                FROM knowledge_items
                ORDER BY updated_at DESC
                LIMIT 10;
            """)
            recent = [dict(r) for r in cur_recent.fetchall()]

            return {
                "total_items": total_items,
                "total_queries": distinct_queries,
                "recent_items": recent,
            }
        except Exception as e:
            return {"error": str(e), "total_items": 0, "total_queries": 0}
