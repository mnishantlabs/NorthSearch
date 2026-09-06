"""Launch the Deep Research web interface."""

from __future__ import annotations

import os
import socket
import threading
import time
import webbrowser

import uvicorn


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def main() -> None:
    host = os.getenv("RESEARCH_HOST", "127.0.0.1")
    port = int(os.getenv("RESEARCH_PORT", "8000"))

    # The datetime filter is registered in webapp.server (used by history).
    from webapp import server as server_module

    url = f"http://{host}:{port}"

    if os.getenv("RESEARCH_NO_BROWSER") != "1":
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()

    print(f"\n  Deep Research web interface: {url}\n")
    uvicorn.run(
        server_module.app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
