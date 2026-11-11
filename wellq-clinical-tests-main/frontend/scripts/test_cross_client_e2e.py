"""Controlled harness checks: no daemon, HTTP server, WSL or application launched."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cross_client_e2e as harness
import cross_client_transport as transport


class CrossClientSafetyTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(tempfile.mkdtemp(prefix="wellq-cross-unit-"))
        self.run_id = "a123456789ab"
        self.project = "wellq-int-" + self.run_id
        self.doc = harness.compose_document(
            self.directory, "sha256:backend", "sha256:mongo", self.run_id
        )
        (self.directory / "compose.json").write_text(json.dumps(self.doc))
        self.manifest = {"project": self.project, "run": self.run_id}

    @staticmethod
    def container(memory=512, running=True):
        return {
            "State": {"Running": running},
            "HostConfig": {"Memory": memory * harness.MIB},
        }

    def test_insufficient_memory_refused(self):
        with self.assertRaisesRegex(RuntimeError, "Insufficient"):
            harness.resource_guard(2882 * harness.MIB, [self.container(2696)])

    def test_unbounded_existing_container_refused(self):
        with self.assertRaisesRegex(RuntimeError, "unverifiable"):
            harness.resource_guard(8192 * harness.MIB, [self.container(0)])

    def test_stopped_container_does_not_reserve_memory(self):
        result = harness.resource_guard(
            2048 * harness.MIB, [self.container(6000, False)]
        )
        self.assertEqual(result["existing_reserved_mib"], 0)

    def test_sufficient_budget(self):
        result = harness.resource_guard(8192 * harness.MIB, [self.container(2696)])
        self.assertEqual(result["new_stack_mib"], 1152)
        self.assertEqual(result["reserve_mib"], 384)

    def test_existing_project_is_rejected(self):
        c = {
            "Config": {"Labels": {"com.docker.compose.project": self.project}},
            "Name": "/anything",
        }
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            harness.project_guard(self.project, [c], [], [])

    def test_old_volume_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Preexisting"):
            harness.project_guard(self.project, [], [self.project + "-mongo-data"], [])

    def test_old_network_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "Preexisting"):
            harness.project_guard(self.project, [], [], [self.project + "-net"])

    def test_unrelated_projects_not_reused_or_managed(self):
        harness.project_guard(self.project, [], ["existing-data"], ["existing-net"])
        for volume in self.doc["volumes"].values():
            self.assertTrue(volume["name"].startswith(self.project + "-"))
            self.assertNotIn("external", volume)

    def test_no_ports_and_internal_network(self):
        self.assertTrue(self.doc["networks"]["isolated"]["internal"])
        for service in self.doc["services"].values():
            self.assertNotIn("ports", service)
            self.assertNotIn("network_mode", service)
            self.assertEqual(service["networks"], ["isolated"])

    def test_images_are_pinned_and_never_pulled(self):
        for service in self.doc["services"].values():
            self.assertIn(service["image"], ("sha256:mongo", "sha256:backend"))
            self.assertEqual(service["pull_policy"], "never")
            self.assertNotIn("build", service)

    def test_explicit_doubles_and_test_identity(self):
        env = self.doc["services"]["api-int"]["environment"]
        self.assertEqual(env["ENVIRONMENT"], "test")
        self.assertEqual(env["WELLQ_INTEGRATION_SCAN_MODE"], "explicit-test-double")
        self.assertEqual(env["JWT_AUDIENCE"], "wellq-integration-only")
        self.assertNotIn("clamav-int", self.doc["services"])
        self.assertIn("${WELLQ_APP_PASSWORD}", env["MONGODB_URI"])

    def test_new_database_and_no_original_runtime_bind(self):
        env = self.doc["services"]["api-int"]["environment"]
        self.assertEqual(env["MONGODB_DB"], "wellq_integration_" + self.run_id)
        text = json.dumps(self.doc)
        self.assertNotIn("/.runtime/", text)
        self.assertNotIn("backend_mongodb_data", text)

    def test_bind_source_normalization(self):
        self.assertTrue(
            harness.same_bind_source(
                "/run/desktop/mnt/host/c/Dev/run/public.pem", "C:\\Dev\\run\\public.pem"
            )
        )
        self.assertFalse(
            harness.same_bind_source(
                "/run/desktop/mnt/host/c/private/public.pem", "C:\\Dev\\run\\public.pem"
            )
        )

    def inspected(self):
        return {
            "Name": "/" + self.project + "-setup-int-1",
            "Image": "sha256:backend",
            "Config": {
                "Labels": {
                    "com.docker.compose.service": "setup-int",
                    "wellq.cross-client": self.run_id,
                }
            },
            "HostConfig": {"PortBindings": {}},
            "NetworkSettings": {"Networks": {self.project + "-net": {}}},
            "Mounts": [
                {
                    "Type": "volume",
                    "Destination": "/" + k,
                    "Name": self.project + "-" + k,
                    "RW": True,
                }
                for k in ("mongo-key", "synthetic-store")
            ],
        }

    def verify(self, container):
        with (
            patch.object(harness, "command", return_value=b"owned-container"),
            patch.object(
                harness,
                "docker_json",
                side_effect=lambda *args: (
                    [container]
                    if args[0] == "inspect"
                    else [{"Labels": {"com.docker.compose.project": self.project}}]
                ),
            ),
        ):
            return harness.verify_owned(self.directory, self.manifest)

    def test_owned_mounts_accepted(self):
        self.assertEqual(len(self.verify(self.inspected())), 1)

    def test_unknown_service_rejected(self):
        c = self.inspected()
        c["Config"]["Labels"]["com.docker.compose.service"] = "unknown"
        with self.assertRaisesRegex(RuntimeError, "Unknown"):
            self.verify(c)

    def test_foreign_volume_rejected(self):
        c = self.inspected()
        c["Mounts"][0]["Name"] = "protected-existing-volume"
        with self.assertRaisesRegex(RuntimeError, "Foreign"):
            self.verify(c)

    def test_published_ports_rejected(self):
        c = self.inspected()
        c["HostConfig"]["PortBindings"] = {"8000/tcp": [{"HostPort": "8000"}]}
        with self.assertRaisesRegex(RuntimeError, "isolation"):
            self.verify(c)

    def test_extra_mount_rejected(self):
        c = self.inspected()
        c["Mounts"].append({"Destination": "/foreign"})
        with self.assertRaisesRegex(RuntimeError, "destinations"):
            self.verify(c)

    def test_transport_routes_fail_closed(self):
        for method, path in (
            ("DELETE", "/api/v1/clinical-tests/x"),
            ("POST", "/api/v1/admin"),
            ("GET", "//external.invalid/"),
            ("GET", "/api/v1/clinical-tests\n"),
            ("GET", "http://external.invalid/"),
            ("GET", "/api/v1/clinical-tests\\x"),
        ):
            with self.subTest(method=method, path=path):
                self.assertFalse(transport.allowed(method, path))

    def test_required_mobile_routes_allowed(self):
        for method, path in (
            ("GET", "/ready"),
            ("GET", "/__wellq_local/adapter.js"),
            ("POST", "/__wellq_local/session"),
            ("POST", "/api/v1/clinical-tests/uploads/initiate"),
            ("PUT", "/object/quarantine/clinical-tests/x?signature=synthetic"),
            ("PATCH", "/api/v1/clinical-tests/x/extraction"),
        ):
            with self.subTest(method=method, path=path):
                self.assertTrue(transport.allowed(method, path))

    def test_redirect_does_not_forward_credentials(self):
        self.assertIsNone(
            transport.NoRedirect().redirect_request(
                None, None, 302, "", {}, "https://external.invalid"
            )
        )

    def test_memory_failure_precedes_any_service_or_listener(self):
        manifest = dict(self.manifest, status="PREPARED_NOT_EXECUTED", source_hashes={})
        (self.directory / "manifest.json").write_text(json.dumps(manifest))
        with (
            patch.object(harness, "RUNS", self.directory.parent),
            patch.object(harness, "source_hashes", return_value={}),
            patch.object(harness, "snapshot", return_value=[self.container(2696)]),
            patch.object(harness, "docker_json", return_value=2882 * harness.MIB),
            patch.object(harness, "command") as mutation,
            patch.object(harness, "ThreadingHTTPServer") as listener,
        ):
            # The safety gate requires the private run-* namespace as well.
            directory = self.directory.parent / ("run-" + self.directory.name)
            directory.mkdir()
            (directory / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError, "Insufficient"):
                harness.run(directory, SimpleNamespace())
            mutation.assert_not_called()
            listener.assert_not_called()
        self.assertEqual(
            json.loads((directory / "manifest.json").read_text())["status"],
            "PREPARED_NOT_EXECUTED",
        )


if __name__ == "__main__":
    unittest.main()
