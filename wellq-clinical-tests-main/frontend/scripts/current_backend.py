"""Run current source read-only in a separate retained integration API container."""
import os
from pathlib import Path
import tempfile
import uuid


def create_api(command, original, backend, project):
    name = project + "-clinical-api-" + uuid.uuid4().hex[:10]
    # Credentials travel via a private temporary file, never Docker arguments/output.
    handle, filename = tempfile.mkstemp(prefix="wellq-clinical-env-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            for entry in original["Config"]["Env"]:
                assert "\n" not in entry and "\r" not in entry
                stream.write(entry + "\n")
        args = ["docker", "create", "--name", name, "--read-only", "--memory", "256m",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                "--tmpfs", "/tmp", "--network", project + "-net", "--env-file", filename,
                "--label", "com.docker.compose.project=" + project,
                "--mount", "type=bind,source=" + str(backend / "app") + ",target=/app/app,readonly"]
        for mount in original["Mounts"]:
            if mount["Type"] == "volume":
                args += ["--mount", "type=volume,source=" + mount["Name"] + ",target=" + mount["Destination"]]
            else:
                source = backend / "integration" / ".runtime" / Path(mount["Source"]).name
                assert source.name in ("public.pem", "gateway.key") and source.is_file()
                args += ["--mount", "type=bind,source=" + str(source) + ",target=" + mount["Destination"] + ",readonly"]
        command(args + [original["Image"], "api"])
    finally:
        Path(filename).unlink(missing_ok=True)
    return name
