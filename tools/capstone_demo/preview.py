"""Read-only compiled portal preview. Never proxies the protected integration API."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

PUBLIC_TYPES = {
    ".html",
    ".js",
    ".css",
    ".svg",
    ".png",
    ".ico",
    ".woff",
    ".woff2",
    ".webmanifest",
}


class Preview(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass  # No URLs, identifiers, tokens or request bodies in access logs.

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        super().end_headers()

    def send_head(self):
        path = unquote(urlsplit(self.path).path)
        if path == "/api" or path.startswith("/api/") or path in {"/health", "/ready"}:
            self.send_error(503, "Independent demo API is not configured")
            return None
        parts = path.split("/")
        if (
            not path.startswith("/")
            or path.startswith(("//", "/__"))
            or "\\" in path
            or any(p.startswith(".") for p in parts if p)
        ):
            self.send_error(404)
            return None
        root = Path(self.directory).resolve()
        target = (root / path.lstrip("/")).resolve()
        if not Path(path).suffix and not path.endswith("/") and not target.is_dir():
            target = (root / "index.html").resolve()
            self.path = "/index.html"
        if path == "/":
            target = (root / "index.html").resolve()
            self.path = "/index.html"
        if not target.is_relative_to(root):
            self.send_error(404)
            return None
        if not target.is_file() or target.suffix not in PUBLIC_TYPES:
            self.send_error(404)
            return None
        return super().send_head()

    def do_POST(self):
        self.send_error(405)

    do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_POST


def server(root, port=9080):
    root = Path(root).resolve(strict=True)
    if not (root / "index.html").is_file():
        raise ValueError("A compiled portal with index.html is required")
    return ThreadingHTTPServer(
        ("127.0.0.1", port), partial(Preview, directory=str(root))
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, required=True)
    args = parser.parse_args()
    with server(args.dist) as httpd:
        print("Compiled portal preview: http://127.0.0.1:9080/clinical; API disabled")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
