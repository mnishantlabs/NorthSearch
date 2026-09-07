"""Search engine provider plugins."""

from research.search.providers.base import SearchProvider
from research.search.providers.bing import BingProvider
from research.search.providers.brave import BraveProvider
from research.search.providers.bunkr import BunkrProvider
from research.search.providers.duckduckgo import DuckDuckGoProvider
from research.search.providers.knowledge import KnowledgeProvider
from research.search.providers.mojeek import MojeekProvider
from research.search.providers.qwant import QwantProvider
from research.search.providers.searxng import SearXNGProvider
from research.search.providers.wikipedia import WikipediaProvider
from research.search.providers.yahoo import YahooProvider
from research.search.providers.yandex import YandexProvider

__all__ = [
    "SearchProvider",
    "DuckDuckGoProvider",
    "BingProvider",
    "YahooProvider",
    "WikipediaProvider",
    "KnowledgeProvider",
    "BraveProvider",
    "SearXNGProvider",
    "YandexProvider",
    "QwantProvider",
    "MojeekProvider",
    "BunkrProvider",
]

PROVIDERS: dict[str, type[SearchProvider]] = {
    "duckduckgo": DuckDuckGoProvider,
    "bing": BingProvider,
    "yahoo": YahooProvider,
    "wikipedia": WikipediaProvider,
    "knowledge": KnowledgeProvider,
    "brave": BraveProvider,
    "searxng": SearXNGProvider,
    "yandex": YandexProvider,
    "qwant": QwantProvider,
    "mojeek": MojeekProvider,
    "bunkr": BunkrProvider,
}