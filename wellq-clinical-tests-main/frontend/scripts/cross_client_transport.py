"""Opt-in WSL/Windows loopback relay. Never logs requests or credentials."""

import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        return None


def allowed(method, path):
    if not path.startswith("/") or path.startswith("//") or "\\" in path:
        return False
    if any(ord(c) <= 32 or ord(c) == 127 for c in path):
        return False
    if method == "GET":
        return path in ("/ready", "/__wellq_local/adapter.js") or path.startswith(
            "/api/v1/clinical-tests"
        )
    if method == "POST":
        return path == "/__wellq_local/session" or path.startswith(
            "/api/v1/clinical-tests/uploads/"
        )
    if method == "PATCH":
        return path.startswith("/api/v1/clinical-tests/") and path.endswith(
            "/extraction"
        )
    return method == "PUT" and path.startswith("/object/quarantine/clinical-tests/")


def windows_request(control, query):
    record = json.loads(Path(control).read_text(encoding="utf-8"))
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    status = urllib.request.Request(
        "http://127.0.0.1:8765/__wellq_local/status",
        headers={"X-WellQ-Control": record["control"]},
    )
    with opener.open(status, timeout=3) as response:
        identity = json.load(response)
    if identity.get("run") != record["run"] or not identity.get("synthetic_only"):
        raise RuntimeError("Unverified bridge identity")
    if not allowed(query["method"], query["path"]):
        raise RuntimeError("Transport route denied")
    body = base64.b64decode(query["body"], validate=True) if query["body"] else None
    if body is not None and len(body) > 1024 * 1024:
        raise RuntimeError("Synthetic payload limit")
    if query["path"] == "/__wellq_local/session" and json.loads(body or b"{}") != {
        "role": "patient"
    }:
        raise RuntimeError("Mobile role denied")
    headers = {
        k: v
        for k, v in query["headers"].items()
        if k.lower()
        in (
            "authorization",
            "content-type",
            "idempotency-key",
            "x-wellq-local",
            "x-goog-if-generation-match",
            "accept",
        )
    }
    request = urllib.request.Request(
        "http://127.0.0.1:8765" + query["path"],
        data=body,
        method=query["method"],
        headers=headers,
    )
    try:
        response = opener.open(request, timeout=40)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        return {
            "status": response.status,
            "body": base64.b64encode(response.read()).decode(),
            "headers": {
                k: v
                for k, v in response.headers.items()
                if k.lower() in ("content-type", "retry-after", "www-authenticate")
            },
        }


def linux_server(python, helper, control):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def relay(self):
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if (
                    not allowed(self.command, self.path)
                    or not 0 <= length <= 1024 * 1024
                ):
                    self.send_error(403)
                    return
                query = {
                    "method": self.command,
                    "path": self.path,
                    "headers": dict(self.headers),
                    "body": base64.b64encode(self.rfile.read(length)).decode(),
                }
                result = subprocess.run(
                    [python, "-B", helper, "--windows", "--control", control],
                    input=json.dumps(query).encode(),
                    capture_output=True,
                    timeout=50,
                    check=False,
                )
                if result.returncode:
                    raise RuntimeError("Owned relay unavailable")
                answer = json.loads(result.stdout)
                body = base64.b64decode(answer["body"], validate=True)
                self.send_response(answer["status"])
                for key, value in answer["headers"].items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (
                OSError,
                ValueError,
                RuntimeError,
                KeyError,
                TypeError,
                subprocess.SubprocessError,
            ):
                self.send_error(502, "Synthetic transport unavailable")

        do_GET = do_POST = do_PATCH = do_PUT = relay

    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler, bind_and_activate=False)
    server.allow_reuse_address = False
    server.server_bind()
    server.server_activate()
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--windows", action="store_true")
    parser.add_argument("--control", required=True)
    args = parser.parse_args()
    try:
        if not args.windows:
            raise RuntimeError("Use the owned Linux runner")
        print(json.dumps(windows_request(args.control, json.load(sys.stdin))))
    except (
        OSError,
        ValueError,
        RuntimeError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ):
        print("Owned synthetic relay refused; details withheld", file=sys.stderr)
        raise SystemExit(1)
