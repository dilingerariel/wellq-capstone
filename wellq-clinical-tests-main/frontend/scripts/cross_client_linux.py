"""Runs only the opt-in cross-client Flutter test in a new Linux source copy."""

import argparse
import hashlib
import json
import os
import signal
import subprocess
import tarfile
import tempfile
import threading
from pathlib import Path

from cross_client_transport import linux_server


def owned_process(argv, **options):
    timeout = options.pop("timeout")
    check = options.pop("check", False)
    # A distinct session lets timeout cleanup target only this runner's group.
    with subprocess.Popen(argv, start_new_session=True, **options) as child:
        try:
            stdout, stderr = child.communicate(timeout=timeout)
        except BaseException:
            for sig, wait in (
                (signal.SIGINT, 10),
                (signal.SIGTERM, 5),
                (signal.SIGKILL, 5),
            ):
                try:
                    os.killpg(child.pid, sig)
                except ProcessLookupError:
                    break
                try:
                    child.communicate(timeout=wait)
                    break
                except subprocess.TimeoutExpired:
                    continue
            raise
        result = subprocess.CompletedProcess(argv, child.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        return result


def main():
    parser = argparse.ArgumentParser()
    for name in (
        "sdk",
        "cache",
        "archive",
        "manifest",
        "control",
        "python",
        "helper",
        "pdfium",
    ):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--stage", choices=("upload", "verify"), required=True)
    args = parser.parse_args()
    source = Path(tempfile.mkdtemp(prefix="wellq-cross-source-"))
    with tarfile.open(args.archive) as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or ".." in path.parts:
                raise RuntimeError("Unsafe source archive")
        archive.extractall(source, filter="data")
    server = linux_server(args.python, args.helper, args.control)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = {
        **os.environ,
        "PUB_CACHE": args.cache,
        "PDFIUM_PATH": args.pdfium,
        "FLUTTER_SUPPRESS_ANALYTICS": "true",
        "WELLQ_CROSS_MANIFEST": args.manifest,
        "WELLQ_CROSS_STAGE": args.stage,
    }
    flutter = str(Path(args.sdk) / "bin/flutter")
    destination = Path(args.manifest).parent
    try:
        version = owned_process(
            [flutter, "--version", "--machine"],
            env=env,
            cwd=source,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
            check=True,
        )
        if json.loads(version.stdout).get("frameworkVersion") != "3.47.9":
            raise RuntimeError("Reviewed Flutter 3.47.9 required")
        with (destination / (args.stage + "-pub.log")).open("wb") as log:
            owned_process(
                [flutter, "pub", "get", "--offline"],
                env=env,
                cwd=source,
                stdout=log,
                stderr=log,
                timeout=120,
                check=True,
            )
        output = destination / (args.stage + "-flutter.jsonl")
        with (
            output.open("wb") as log,
            (destination / (args.stage + "-flutter.stderr")).open("wb") as err,
        ):
            result = owned_process(
                [
                    flutter,
                    "test",
                    "--no-pub",
                    "--concurrency=1",
                    "--machine",
                    "--dart-define=WELLQ_CROSS_E2E=true",
                    "test/cross_client_e2e_test.dart",
                ],
                env=env,
                cwd=source,
                stdout=log,
                stderr=err,
                timeout=540,
            )
        events = []
        for line in output.read_text().splitlines():
            try:
                event = json.loads(line)
                if isinstance(event, dict):
                    events.append(event)
            except ValueError:
                pass
        done = [
            e for e in events if e.get("type") == "testDone" and not e.get("hidden")
        ]
        passed = (
            result.returncode == 0
            and len(done) == 1
            and all(e["result"] == "success" and not e["skipped"] for e in done)
            and any(e.get("type") == "done" and e.get("success") for e in events)
        )
        summary = {
            "stage": args.stage,
            "passed": passed,
            "tests": len(done),
            "source_sha256": hashlib.sha256(
                Path(args.archive).read_bytes()
            ).hexdigest(),
            "environment": "Linux Flutter 3.47.9; no Android execution",
        }
        (destination / (args.stage + "-summary.json")).write_text(
            json.dumps(summary, indent=2)
        )
        if not passed:
            raise RuntimeError("Cross-client Flutter stage failed")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        RuntimeError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ):
        raise SystemExit(
            "Cross-client Linux stage failed; inspect private run evidence"
        )
