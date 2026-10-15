"""Launch the traffic network designer in a browser (standard library only).

    python3 traffic_tree_toy.py
    python3 traffic_tree_toy.py --no-browser --port 8000

The original Tkinter version is preserved in traffic_tree_tk.py.
"""
from __future__ import annotations

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import webbrowser

PAGE = Path(__file__).with_name("traffic_tree_toy.html")


class TrafficHandler(BaseHTTPRequestHandler):
    """Serve only the application, never the surrounding workspace."""

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] not in ("/", "/traffic_tree_toy.html"):
            self.send_error(404)
            return
        content = PAGE.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="Local port (default: choose a free port)")
    parser.add_argument("--no-browser", action="store_true", help="Print the URL without opening a browser")
    args = parser.parse_args()
    if not PAGE.is_file():
        parser.error(f"Missing webpage: {PAGE}")
    try:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), TrafficHandler)
    except OSError as exc:
        parser.error(f"Cannot start local server: {exc}")
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Traffic Tree Toy: {url}\nKeep this terminal open. Press Ctrl+C to stop.", flush=True)
    if not args.no_browser:
        # Start accepting requests before the browser connects.
        timer = threading.Timer(0.2, partial(webbrowser.open, url))
        timer.daemon = True
        timer.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
