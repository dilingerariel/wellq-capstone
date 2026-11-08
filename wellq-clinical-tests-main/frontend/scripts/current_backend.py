"""Run current source read-only in a separate retained integration API container."""

import os
import io
import json
from pathlib import Path
import tarfile
import tempfile
import uuid


def create_api(command, original, backend, project):
    try:
        image = json.loads(command(["docker", "image", "inspect", original["Image"]]))[
            0
        ]
        replacement = False
    except RuntimeError:
        # A rebuild can leave retained containers usable but their old image ID
        # absent from Desktop's image store. Never pull or accept an arbitrary tag.
        assert original["Config"]["Image"] == project + "-backend"
        image = json.loads(
            command(["docker", "image", "inspect", project + "-backend"])
        )[0]
        labels = image["Config"].get("Labels") or {}
        assert labels.get("com.docker.compose.project") == project
        assert labels.get("com.docker.compose.service") == "api-int"
        for setting in ("Entrypoint", "WorkingDir", "User"):
            assert image["Config"][setting] == original["Config"][setting]
        replacement = True
    name = project + "-clinical-api-" + uuid.uuid4().hex[:10]
    # Credentials travel via a private temporary file, never Docker arguments/output.
    handle, filename = tempfile.mkstemp(prefix="wellq-clinical-env-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            for entry in original["Config"]["Env"]:
                assert "\n" not in entry and "\r" not in entry
                stream.write(entry + "\n")
        args = [
            "docker",
            "create",
            "--name",
            name,
            "--read-only",
            "--memory",
            "256m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--tmpfs",
            "/tmp",
            "--network",
            project + "-net",
            "--env-file",
            filename,
            "--label",
            "com.docker.compose.project=" + project,
            "--mount",
            "type=bind,source=" + str(backend / "app") + ",target=/app/app,readonly",
        ]
        for mount in original["Mounts"]:
            if mount["Type"] == "volume":
                args += [
                    "--mount",
                    "type=volume,source="
                    + mount["Name"]
                    + ",target="
                    + mount["Destination"],
                ]
            else:
                source = (
                    backend / "integration" / ".runtime" / Path(mount["Source"]).name
                )
                assert source.name in ("public.pem", "gateway.key") and source.is_file()
                args += [
                    "--mount",
                    "type=bind,source="
                    + str(source)
                    + ",target="
                    + mount["Destination"]
                    + ",readonly",
                ]
        command(args + [image["Id"], "api"])
        if replacement:
            # Before starting anything, prove dependencies and integration runtime
            # match this checkout. The product app is mounted read-only below.
            for relative in ("requirements.txt", "requirements-dev.txt", "integration"):
                archive = command(["docker", "cp", name + ":/app/" + relative, "-"])
                with tarfile.open(fileobj=io.BytesIO(archive)) as entries:
                    matched = 0
                    for member in entries.getmembers():
                        if not member.isfile() or "/tests/" in member.name:
                            continue
                        if relative == "integration" and not member.name.endswith(
                            ".py"
                        ):
                            continue
                        current = backend / member.name
                        assert current.is_file()
                        assert current.read_bytes().replace(
                            b"\r\n", b"\n"
                        ) == entries.extractfile(member).read().replace(b"\r\n", b"\n")
                        matched += 1
                    assert matched > 0
    finally:
        Path(filename).unlink(missing_ok=True)
    return name, image["Id"]
