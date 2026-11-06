from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, unquote
import json
from integration.adapters import object_path, verify_signature


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Never log signed URLs.

    def handle_object(self, method):
        parsed = urlsplit(self.path)
        key = unquote(parsed.path.removeprefix("/object/"))
        params = parse_qs(parsed.query)
        try:
            valid = verify_signature(key, method, params["expiry"][0], params["signature"][0])
            path = object_path(key)
        except (ValueError, KeyError):
            valid = False
        if not valid or (method == "GET" and not key.startswith("private/")):
            self.send_error(403); return
        if method == "PUT":
            if not key.startswith("quarantine/") or self.headers.get("x-goog-if-generation-match") != "0":
                self.send_error(403); return
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 20 * 1024 * 1024:
                self.send_error(413); return
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with path.open("xb") as f:
                    f.write(self.rfile.read(length))
            except FileExistsError:
                self.send_error(412); return
            path.with_name(path.name + ".meta").write_text(json.dumps({"generation": 1, "mime": self.headers["Content-Type"]}))
            self.send_response(200); self.end_headers()
        elif path.exists():
            self.send_response(200); self.end_headers(); self.wfile.write(path.read_bytes())
        else:
            self.send_error(404)

    def do_PUT(self):
        self.handle_object("PUT")

    def do_GET(self):
        self.handle_object("GET")


def main():
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
