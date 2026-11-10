"""Isolated bridge-procedure tests: no real Docker, sockets, ADB or signing."""

import copy
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import local_web as web


class BridgeProcedureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)
        self.project = "wellq-int-test123"
        self.state = {
            "run": "test123",
            "project": self.project,
            "db": "wellq_integration_test123",
        }
        self.fixture = {
            "tenant": "synthetic-local-test",
            "patient": "synthetic-local-patient-test",
            "clinician": "synthetic-local-clinician-test",
        }
        (self.runtime / "state.json").write_text(json.dumps(self.state))
        self.fixture_path = self.runtime / "fixture.json"
        self.fixture_path.write_text(json.dumps(self.fixture))
        self.containers = {}
        for i, (suffix, service, number) in enumerate(web.BRIDGE_SERVICES):
            env = {
                "ENVIRONMENT": "test",
                "MONGODB_DB": self.state["db"],
                "MONGODB_URI": "mongodb://redacted@mongo-int:27017/"
                + self.state["db"]
                + "?replicaSet=wellqIntRs",
                "JWT_ISSUER": "https://identity.wellq-integration.invalid",
                "JWT_AUDIENCE": "wellq-integration-only",
                "CLAMAV_HOST": "clamav-int",
            }
            name = self.project + "-" + suffix
            self.containers[name] = {
                "Id": "verified-id-" + str(i),
                "Name": "/" + name,
                "Image": "sha256:6d87c712e3391e13c1ba6e05dfb074d4b1ddb5a6834b23bb9da990d2a4ef042a"
                if service == "clamav-int"
                else "owned-image",
                "Config": {
                    "Image": "clamav/clamav:stable"
                    if service == "clamav-int"
                    else "owned-image",
                    "Labels": {
                        "com.docker.compose.project": self.project,
                        "com.docker.compose.service": service,
                        "com.docker.compose.container-number": number,
                    },
                    "Env": [k + "=" + v for k, v in env.items()],
                },
                "HostConfig": {"PortBindings": {}, "Privileged": False},
                "NetworkSettings": {"Networks": {self.project + "-net": {}}},
                "State": {"Running": True, "Health": {"Status": "healthy"}},
                "Mounts": [
                    {
                        "Type": "volume",
                        "Name": self.project + "-clam-signatures",
                        "Destination": "/var/lib/clamav",
                        "RW": True,
                    }
                ]
                if service == "clamav-int"
                else [],
            }
        self.active = list(self.containers.values())
        self.commands = []
        self.volume_project = self.project
        self.archive = self.source_archive()
        self.read_status = web.status
        for target, value in (
            ("RUNTIME", self.runtime),
            ("FIXTURE", self.fixture_path),
            ("CONTROL", self.runtime / "control.json"),
            ("inspect", lambda name: copy.deepcopy(self.containers[name])),
            ("command", self.fake_command),
            ("status", Mock(return_value=None)),
            ("container_python", Mock(return_value={"ready": True})),
        ):
            p = patch.object(web, target, value)
            p.start()
            self.addCleanup(p.stop)
        # Any missed mock must fail before touching real services or networking.
        for name in ("subprocess.run", "subprocess.Popen", "socket.socket"):
            p = patch(
                name,
                side_effect=AssertionError("Real I/O forbidden in controlled tests"),
            )
            p.start()
            self.addCleanup(p.stop)

    def source_archive(self, stale=False):
        data = io.BytesIO()
        sources = sorted((web.BACK / "app").rglob("*.py"))[:35]
        self.assertEqual(len(sources), 35)
        with tarfile.open(fileobj=data, mode="w") as archive:
            for i, path in enumerate(sources):
                content = b"stale source" if stale and i == 0 else path.read_bytes()
                entry = tarfile.TarInfo(path.relative_to(web.BACK).as_posix())
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
        return data.getvalue()

    def fake_command(self, args, *unused, **kwargs):
        self.commands.append(args)
        if args[:3] == ["docker", "volume", "inspect"]:
            return json.dumps(
                [{"Labels": {"com.docker.compose.project": self.volume_project}}]
            ).encode()
        if args == ["docker", "ps", "-q"]:
            return " ".join(c["Id"] for c in self.active).encode()
        if args[:2] == ["docker", "inspect"]:
            return json.dumps(self.active).encode()
        if args[:2] == ["docker", "cp"]:
            return self.archive
        raise AssertionError("Unapproved command in controlled test")

    @property
    def clam(self):
        return self.containers[self.project + "-clamav-int-1"]

    def owned(self):
        return web.owned(bridge_only=True)

    def test_exact_verified_six_services_and_source_are_accepted(self):
        _, names = self.owned()
        self.assertEqual(
            names,
            [
                self.project + "-" + s
                for s in (
                    "mongo-int-1",
                    "objects-int-1",
                    "api-int-1",
                    "worker-int-1",
                    "worker-int-2",
                    "clamav-int-1",
                )
            ],
        )
        self.assertTrue(any(c[:2] == ["docker", "cp"] for c in self.commands))

    def test_wrong_container_name_is_rejected(self):
        self.clam["Name"] = "/unknown"
        with self.assertRaises(AssertionError):
            self.owned()

    def test_wrong_project_service_or_replica_identity_is_rejected(self):
        for key in ("project", "service", "container-number"):
            with self.subTest(label=key):
                field = "com.docker.compose." + key
                old = self.clam["Config"]["Labels"][field]
                self.clam["Config"]["Labels"][field] = "unknown"
                with self.assertRaises(AssertionError):
                    self.owned()
                self.clam["Config"]["Labels"][field] = old

    def test_wrong_or_additional_network_is_rejected(self):
        self.clam["NetworkSettings"]["Networks"]["external"] = {}
        with self.assertRaises(AssertionError):
            self.owned()

    def test_published_port_is_rejected(self):
        self.clam["HostConfig"]["PortBindings"] = {"3310/tcp": [{"HostPort": "3310"}]}
        with self.assertRaises(AssertionError):
            self.owned()

    def test_unverified_clamav_image_is_rejected(self):
        self.clam["Image"] = "sha256:unknown"
        with self.assertRaises(AssertionError):
            self.owned()

    def test_unexpected_clamav_tag_is_rejected(self):
        self.clam["Config"]["Image"] = "unknown/clamav:stable"
        with self.assertRaises(AssertionError):
            self.owned()

    def test_privileged_clamav_is_rejected(self):
        self.clam["HostConfig"]["Privileged"] = True
        with self.assertRaises(AssertionError):
            self.owned()

    def test_unexpected_antivirus_mount_is_rejected(self):
        self.clam["Mounts"][0]["Destination"] = "/unexpected"
        with self.assertRaises(AssertionError):
            self.owned()

    def test_additional_antivirus_mount_is_rejected(self):
        self.clam["Mounts"].append({"Type": "bind", "Destination": "/extra"})
        with self.assertRaises(AssertionError):
            self.owned()

    def test_wrong_volume_ownership_is_rejected(self):
        self.volume_project = "another-project"
        with self.assertRaises(AssertionError):
            self.owned()

    def test_stopped_or_unhealthy_services_are_not_started(self):
        for name in self.containers:
            with self.subTest(container=name):
                self.containers[name]["State"]["Running"] = False
                with self.assertRaises(AssertionError):
                    self.owned()
                self.containers[name]["State"]["Running"] = True
        self.clam["State"]["Health"]["Status"] = "starting"
        with self.assertRaises(AssertionError):
            self.owned()
        self.assertFalse(any(c[:2] == ["docker", "start"] for c in self.commands))

    def test_incorrect_synthetic_configuration_is_rejected(self):
        api = self.containers[self.project + "-api-int-1"]
        original = api["Config"]["Env"][:]
        for key in (
            "ENVIRONMENT",
            "MONGODB_DB",
            "MONGODB_URI",
            "JWT_ISSUER",
            "JWT_AUDIENCE",
            "CLAMAV_HOST",
        ):
            with self.subTest(key=key):
                api["Config"]["Env"] = [
                    v for v in original if not v.startswith(key + "=")
                ] + [key + "=unexpected"]
                with self.assertRaises(AssertionError):
                    self.owned()
        api["Config"]["Env"] = original

    def test_unknown_active_container_is_rejected_even_if_unrelated(self):
        extra = copy.deepcopy(self.clam)
        extra["Name"] = "/unknown"
        extra["Id"] = "unknown"
        extra["Config"]["Labels"]["com.docker.compose.project"] = "other"
        extra["NetworkSettings"]["Networks"] = {"other-net": {}}
        extra["Mounts"] = []
        self.active.append(extra)
        with self.assertRaisesRegex(RuntimeError, "Another integration task"):
            self.owned()

    def test_container_replacement_during_inspection_is_rejected(self):
        self.active = copy.deepcopy(self.active)
        self.active[0]["Id"] = "replacement"
        with self.assertRaises(AssertionError):
            self.owned()

    def test_disappearing_service_is_rejected(self):
        self.active.pop()
        with self.assertRaises(AssertionError):
            self.owned()

    def test_stale_backend_source_is_rejected(self):
        self.archive = self.source_archive(stale=True)
        with self.assertRaisesRegex(AssertionError, "stale"):
            self.owned()

    def test_historical_five_service_behavior_is_preserved(self):
        self.active = self.active[:-1]
        _, names = web.owned()
        self.assertEqual(len(names), 5)
        self.assertNotIn(self.project + "-clamav-int-1", names)

    def test_preparation_reads_ready_without_seeding_or_changing_fixture(self):
        before = self.fixture_path.read_bytes()
        names, fixture = web.prepare_bridge_only()
        self.assertEqual(len(names), 6)
        self.assertEqual(fixture, self.fixture)
        self.assertEqual(self.fixture_path.read_bytes(), before)
        args = web.container_python.call_args.args
        self.assertIn("/ready", args[1])
        self.assertNotIn("database", args[1])

    def test_missing_fixture_is_not_created(self):
        self.fixture_path.unlink()  # Only the temporary test fixture, never project data.
        with self.assertRaisesRegex(RuntimeError, "never seeds"):
            web.prepare_bridge_only()
        self.assertFalse(self.fixture_path.exists())

    def test_wrong_identity_is_rejected(self):
        self.fixture_path.write_text(
            json.dumps({**self.fixture, "patient": "real-patient"})
        )
        with self.assertRaisesRegex(RuntimeError, "identity"):
            web.prepare_bridge_only()

    def test_existing_bridge_is_not_replaced(self):
        web.status.return_value = {"ready": True}
        with self.assertRaisesRegex(RuntimeError, "not be replaced"):
            web.prepare_bridge_only()
        self.assertEqual(self.commands, [])

    def test_not_ready_api_is_not_repaired(self):
        web.container_python.return_value = {"ready": False}
        with self.assertRaisesRegex(RuntimeError, "will not change"):
            web.prepare_bridge_only()

    def run_fake_server(self, bind_error=None, status=200):
        host = Mock()
        host.forward.return_value = {"status": status}
        host.seed.side_effect = AssertionError("Seeds forbidden")
        host.control = "private-test-control"
        host.run = "test-run"
        server = Mock()
        server.server_bind.side_effect = bind_error
        server.serve_forever.side_effect = KeyboardInterrupt
        with (
            patch.object(
                web,
                "prepare_bridge_only",
                return_value=(list(self.containers), self.fixture),
            ),
            patch.object(web, "ThreadingHTTPServer", return_value=server) as factory,
            patch.object(web, "LocalHost", return_value=host) as constructor,
            patch.object(web, "save") as save,
            patch.object(
                web, "services", side_effect=AssertionError("Service start forbidden")
            ),
        ):
            error = None
            try:
                web.serve_bridge_only()
            except (OSError, RuntimeError) as e:
                error = e
        return host, server, factory, constructor, save, error

    def test_bridge_only_binds_loopback_no_vite_seed_or_docker_lifecycle(self):
        host, server, factory, _constructor, save, error = self.run_fake_server()
        self.assertIsNone(error)
        self.assertEqual(factory.call_args.args[0], ("127.0.0.1", 8765))
        self.assertFalse(factory.call_args.kwargs["bind_and_activate"])
        host.forward.assert_called_once_with("/ready")
        host.seed.assert_not_called()
        server.server_activate.assert_called_once()
        server.server_close.assert_called_once()
        host.relay.stdin.close.assert_called_once()
        host.relay.wait.assert_called_once()
        self.assertEqual(save.call_args.args[0], web.CONTROL)
        self.assertEqual(save.call_args.args[1]["mode"], "bridge-only")
        self.assertEqual(self.commands, [])

    def test_occupied_port_does_not_create_transport_or_replace_process(self):
        host, server, _, constructor, save, error = self.run_fake_server(
            bind_error=OSError("occupied")
        )
        self.assertIsInstance(error, OSError)
        constructor.assert_not_called()
        save.assert_not_called()
        server.server_close.assert_called_once()
        host.relay.terminate.assert_not_called()

    def test_windows_bridge_reserves_port_exclusively_before_binding(self):
        with (
            patch.object(web, "os", SimpleNamespace(name="nt", getpid=web.os.getpid)),
            patch.object(web.socket, "SO_EXCLUSIVEADDRUSE", 123, create=True),
        ):
            _, server, _, _, _, error = self.run_fake_server()
        self.assertIsNone(error)
        self.assertFalse(server.allow_reuse_address)
        self.assertEqual(server.method_calls[0].args, (web.socket.SOL_SOCKET, 123, 1))
        self.assertEqual(server.method_calls[0][0], "socket.setsockopt")
        self.assertEqual(server.method_calls[1][0], "server_bind")

    def test_api_failure_closes_only_own_transport_and_never_serves(self):
        host, server, _, _, save, error = self.run_fake_server(status=503)
        self.assertIsInstance(error, RuntimeError)
        server.server_activate.assert_not_called()
        save.assert_not_called()
        host.relay.stdin.close.assert_called_once()
        host.seed.assert_not_called()

    def test_bad_identity_key_is_rejected_before_process_creation(self):
        key = Mock()
        key.key_size = 2048
        key.public_key.return_value.public_bytes.return_value = b"different-public-key"
        with (
            patch.object(Path, "read_bytes", return_value=b"test-public-key"),
            patch.object(web.serialization, "load_pem_private_key", return_value=key),
            patch.object(web.subprocess, "Popen") as popen,
        ):
            with self.assertRaises(AssertionError):
                web.LocalHost(list(self.containers), self.fixture)
            popen.assert_not_called()

    def test_bridge_stop_uses_only_matching_private_control_no_docker_or_adb(self):
        web.status.return_value = {"run": "test-run"}
        web.CONTROL.write_text(
            json.dumps(
                {"mode": "bridge-only", "run": "test-run", "control": "test-control"}
            )
        )
        with patch.object(
            web.LOCAL_HTTP, "open", return_value=Mock(__enter__=Mock(), __exit__=Mock())
        ) as request:
            web.stop_bridge_only()
        target = request.call_args.args[0]
        self.assertEqual(target.full_url, "http://127.0.0.1:8765/__wellq_local/stop")
        self.assertEqual(target.get_method(), "POST")
        self.assertEqual(self.commands, [])

    def test_bridge_stop_refuses_full_host_or_changed_run(self):
        for mode, run in (("full", "test-run"), ("bridge-only", "other")):
            with self.subTest(mode=mode, run=run):
                web.status.return_value = {"run": "test-run"}
                web.CONTROL.write_text(json.dumps({"mode": mode, "run": run}))
                with self.assertRaisesRegex(RuntimeError, "not this bridge-only"):
                    web.stop_bridge_only()

    def test_cli_routes_recovery_without_historical_start_stop(self):
        for action, function in (
            ("bridge-only", "serve_bridge_only"),
            ("bridge-stop", "stop_bridge_only"),
        ):
            with (
                self.subTest(action=action),
                patch.object(sys, "argv", ["local_web.py", action]),
                patch.object(web, function) as target,
                patch.object(
                    web,
                    "services",
                    side_effect=AssertionError("Docker lifecycle forbidden"),
                ),
                patch.object(
                    web,
                    "serve",
                    side_effect=AssertionError("Historical startup forbidden"),
                ),
            ):
                web.main()
                target.assert_called_once()

    def test_legacy_start_stop_refuse_active_bridge_without_touching_services(self):
        web.CONTROL.write_text(
            json.dumps(
                {"mode": "bridge-only", "run": "test-run", "control": "test-control"}
            )
        )
        for action in ("start", "stop"):
            with (
                self.subTest(action=action),
                patch.object(sys, "argv", ["local_web.py", action]),
                patch.object(web, "owned") as owned,
                patch.object(web, "status", self.read_status),
                patch.object(web.LOCAL_HTTP, "open") as request,
            ):
                request.return_value.__enter__.return_value.read.return_value = (
                    '{"run":"test-run","ready":true}'
                )
                with self.assertRaisesRegex(RuntimeError, "Use bridge-stop"):
                    web.main()
                owned.assert_not_called()
        self.assertEqual(self.commands, [])

    def test_handler_never_logs_request_credentials_or_content(self):
        handler = object.__new__(web.handler(Mock()))
        with (
            patch("sys.stdout", new_callable=io.StringIO) as stdout,
            patch("sys.stderr", new_callable=io.StringIO) as stderr,
        ):
            handler.log_message("test-private-jwt test-clinical-data")
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
