"""Local HTTP tests with a temporary synthetic build; no application services."""

import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from preview import server


class PreviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root / "index.html").write_text("SYNTHETIC COMPILED PORTAL", encoding="utf-8")
        (root / "key.pem").write_text("SYNTHETIC DENIED FILE", encoding="utf-8")
        self.httpd = server(root, 0)
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.start()
        self.origin = "http://127.0.0.1:" + str(self.httpd.server_port)

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join()
        self.httpd.server_close()
        self.temp.cleanup()

    def status(self, path, method="GET"):
        try:
            with urlopen(Request(self.origin + path, method=method), timeout=3) as r:
                return r.status
        except HTTPError as e:
            e.close()
            return e.code

    def test_compiled_entry_loopback_and_no_cache(self):
        self.assertEqual(self.httpd.server_address[0], "127.0.0.1")
        with urlopen(self.origin + "/clinical", timeout=3) as r:
            self.assertIn(b"SYNTHETIC COMPILED PORTAL", r.read())
            self.assertEqual(r.headers["Cache-Control"], "no-store")

    def test_no_api_or_integration_proxy(self):
        for path in ["/api", "/api/v1/clinical-tests", "/health", "/ready"]:
            with self.subTest(path=path):
                self.assertEqual(self.status(path), 503)

    def test_no_identity_keys_traversal_or_directory_listing(self):
        for path in [
            "/__wellq_local/adapter.js",
            "/key.pem",
            "/%2e%2e/key.pem",
            "/assets/",
            "/.runtime/secret",
        ]:
            with self.subTest(path=path):
                self.assertEqual(self.status(path), 404)

    def test_no_mutations(self):
        for method in ["POST", "PUT", "PATCH", "DELETE"]:
            with self.subTest(method=method):
                self.assertEqual(self.status("/api/v1/clinical-tests", method), 405)


if __name__ == "__main__":
    unittest.main()
