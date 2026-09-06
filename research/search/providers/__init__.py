"""Search engine provider plugins."""

from research.search.providers.base import SearchProvider
from research.search.providers.bing import BingProvider
from research.search.providers.brave import BraveProvider
from research.search.providers.duckduckgo import DuckDuckGoProvider
from research.search.providers.searxng import SearXNGProvider

__all__ = [
    "SearchProvider",
    "DuckDuckGoProvider",
    "BraveProvider",
    "BingProvider",
    "SearXNGProvider",
]

PROVIDERS: dict[str, type[SearchProvider]] = {
    "duckduckgo": DuckDuckGoProvider,
    "brave": BraveProvider,
    "bing": BingProvider,
    "searxng": SearXNGProvider,
}