"""Prepare new release sources only; never build or edit the development tree."""

import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

PREFIX = "wellq-clinical-tests-main/mobile/"
ROOT_FILES = {
    "pubspec.yaml",
    "pubspec.lock",
    "l10n.yaml",
    "analysis_options.yaml",
    ".metadata",
}
SOURCE_DIRS = {"lib", "android", "ios", "windows", "linux", "macos"}
ASSET_BLOCK = "  assets:\n    - assets/synthetic.pdf\n"


def release_manifest(content):
    text = content.decode("utf-8").replace("\r\n", "\n")
    # Deliberately support only today's sole asset declaration. Refuse future
    # manifest changes rather than silently removing other required assets.
    if text.count("  assets:\n") != 1 or not text.endswith(ASSET_BLOCK):
        raise ValueError(
            "Unexpected asset configuration; review preparation before release"
        )
    return text[: -len(ASSET_BLOCK)].encode("utf-8")


def prepare(archive_bytes, destination, commit):
    destination = Path(destination)
    if destination.exists():
        raise ValueError("Destination exists; no overwrite permitted")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive_bytes)) as archive:
        for member in archive.getmembers():
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts or "\\" in member.name:
                raise ValueError("Unsafe archive path")
            if member.isdir():
                continue
            if not member.isfile() or not member.name.startswith(PREFIX):
                raise ValueError("Unexpected archive entry")
            relative = PurePosixPath(member.name[len(PREFIX) :])
            if (
                relative.as_posix() not in ROOT_FILES
                and relative.parts[0] not in SOURCE_DIRS
            ):
                continue  # No assets, tests, tools, .runtime or local build caches.
            if relative.suffix.lower() in {
                ".pdf",
                ".pem",
                ".key",
                ".p12",
                ".pfx",
                ".jks",
                ".keystore",
                ".sqlite",
            } or relative.name in {"local.properties", "key.properties", ".env"}:
                raise ValueError(
                    "Private/test resource inside source selection; review required"
                )
            if relative.as_posix() in files:
                raise ValueError("Duplicate archive entry")
            files[relative.as_posix()] = archive.extractfile(member).read()
    if not {"pubspec.yaml", "lib/main.dart"} <= files.keys():
        raise ValueError("Required source files missing")
    files["pubspec.yaml"] = release_manifest(files["pubspec.yaml"])
    destination.mkdir(parents=True, exist_ok=False)
    for name, content in files.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            output.write(content)
    record = {
        "status": "SOURCES_PREPARED_NOT_BUILT",
        "source_commit": commit,
        "excluded_asset": "assets/synthetic.pdf",
        "files": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(files.items())
        },
    }
    with (destination / "release-source.json").open("x", encoding="utf-8") as output:
        json.dump(record, output, indent=2)
    return record


def main():
    repo = Path(__file__).resolve().parents[3]

    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args])

    if git("status", "--porcelain").strip():
        raise ValueError(
            "Worktree must be clean; preparation uses committed sources only"
        )
    commit = git("rev-parse", "HEAD").decode().strip()
    archive = git("archive", "--format=tar", commit, PREFIX.rstrip("/"))
    parent = repo / ".venv/wellq-mobile-release-source"
    parent.mkdir(parents=True, exist_ok=True)
    # mkdtemp reserves a new parent; prepare requires an absent child directory.
    destination = Path(tempfile.mkdtemp(prefix="run-", dir=parent)) / "mobile"
    prepare(archive, destination, commit)
    print("Prepared sources only; no APK/AAB built: " + str(destination))


if __name__ == "__main__":
    main()
