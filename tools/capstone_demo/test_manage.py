"""Prepare only temporary deployment files. Never calls Docker or provisions DB."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from manage import build_portal, prepare, traffic_policy


class PlanTest(unittest.TestCase):
    def test_demo_build_is_scoped_and_does_not_change_parent_environment(self):
        import os
        import sys

        from manage import BACK

        sys.path.insert(0, str(BACK))
        from integration.capstone_gateway import validate_portal

        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            before = dict(os.environ)
            calls = []

            def fake_build(command, **kwargs):
                calls.append((command, kwargs))
                (folder / "portal").mkdir()
                (folder / "portal/index.html").write_text(
                    "<html>COMPILED SYNTHETIC</html>"
                )

            build_portal(folder, "wellq-int-capstone-build-test", fake_build)
            self.assertEqual(os.environ, before)
            self.assertEqual(calls[0][1]["env"]["NODE_ENV"], "development")
            self.assertEqual(calls[0][1]["env"]["VITE_DATA_MODE"], "api")
            self.assertEqual(calls[0][1]["env"]["WELLQ_LOCAL_INTEGRATION"], "0")
            validate_portal(folder / "portal", "wellq-int-capstone-build-test")
            with self.assertRaises(ValueError):
                validate_portal(folder / "portal", "wellq-int-39706292db88")
            with self.assertRaises(ValueError):
                build_portal(folder, "wellq-int-capstone-build-test", fake_build)
            (folder / "portal/index.html").write_text("CHANGED")
            with self.assertRaises(ValueError):
                validate_portal(folder / "portal", "wellq-int-capstone-build-test")

    def test_new_projects_keys_and_volumes_are_independent(self):
        with tempfile.TemporaryDirectory() as temp:
            first = prepare(base=Path(temp))
            second = prepare(base=Path(temp))
            self.assertNotEqual(first.name, second.name)
            self.assertNotEqual(
                (first / "private.pem").read_bytes(),
                (second / "private.pem").read_bytes(),
            )
            plan = json.loads((first / "compose.json").read_text())
            self.assertTrue(plan["name"].startswith("wellq-int-capstone-"))
            self.assertNotIn("39706292db88", json.dumps(plan))
            self.assertTrue(plan["networks"]["private"]["internal"])
            self.assertEqual(
                set(plan["services"]["clamav-int"]["networks"]),
                {"private", "av-update"},
            )
            self.assertEqual(
                [s for s, c in plan["services"].items() if c.get("ports")], ["gateway"]
            )
            self.assertEqual(
                plan["services"]["gateway"]["ports"], ["127.0.0.1:9080:9080"]
            )
            for v in plan["volumes"].values():
                self.assertTrue(v["name"].startswith(plan["name"]))
                self.assertNotIn("external", v)
            for name, service in plan["services"].items():
                if name not in ("mongo-int", "clamav-int", "setup-int"):
                    self.assertEqual(service["environment"]["ENVIRONMENT"], "test")
                    self.assertEqual(
                        service["environment"]["CATALOG_CLINICALLY_APPROVED"], "false"
                    )
                if name != "gateway":
                    self.assertNotIn("/demo/private.pem", json.dumps(service))
            c = json.loads((first / "gateway.json").read_text())
            codes = json.loads((first / "participant-passes.private.json").read_text())
            self.assertEqual(len(c["profiles"]), 4)
            self.assertEqual(len({p["tenant"] for p in c["profiles"]}), 2)
            for code in codes.values():
                self.assertNotIn(code, json.dumps(c))
                self.assertIn(
                    hashlib.sha256(code.encode()).hexdigest(),
                    [p["code_hash"] for p in c["profiles"]],
                )

    def test_ngrok_defaults_closed_and_no_worldwide_allowlist(self):
        for cidrs in [[], ["0.0.0.0/0"], ["::/0"], ["invalid"]]:
            with self.assertRaises(ValueError):
                traffic_policy(cidrs)
        policy = traffic_policy(["203.0.113.7/32", "2001:db8::7/128"])
        config = policy["on_http_request"][0]["actions"][0]["config"]
        self.assertTrue(config["enforce"])
        self.assertEqual(len(config["allow"]), 2)


if __name__ == "__main__":
    unittest.main()
