"""Small in-memory archives and fresh temporary folders; no Flutter or services."""

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

from prepare_release_source import ASSET_BLOCK, PREFIX, prepare, release_manifest


def archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as output:
        for name, content in entries.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            output.addfile(entry, io.BytesIO(content))
    return stream.getvalue()


class ReleaseSourceTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="wellq-release-unit-"))
        self.destination = self.root / "prepared"
        self.manifest = (
            b"name: synthetic_test\nflutter:\n  generate: true\n" + ASSET_BLOCK.encode()
        )
        self.entries = {
            PREFIX + "pubspec.yaml": self.manifest,
            PREFIX + "lib/main.dart": b"// unchanged production block and identity\n",
            PREFIX + "android/app/build.gradle.kts": b"// unchanged package/signing\n",
            PREFIX + "assets/synthetic.pdf": b"SYNTHETIC UNIT FIXTURE",
            PREFIX + "test/fixture.dart": b"test only",
            PREFIX + ".runtime/private.pem": b"test placeholder",
            PREFIX + "tool/create_fixture.py": b"not a production input",
        }

    def test_only_prepared_copy_omits_fixture_and_keeps_sources_intact(self):
        original = archive(self.entries)
        result = prepare(original, self.destination, "unit-commit")
        self.assertEqual(self.entries[PREFIX + "pubspec.yaml"], self.manifest)
        self.assertEqual(
            (self.destination / "pubspec.yaml").read_bytes(),
            release_manifest(self.manifest),
        )
        self.assertNotIn(
            "synthetic.pdf", (self.destination / "pubspec.yaml").read_text()
        )
        self.assertEqual(
            (self.destination / "lib/main.dart").read_bytes(),
            self.entries[PREFIX + "lib/main.dart"],
        )
        self.assertEqual(
            (self.destination / "android/app/build.gradle.kts").read_bytes(),
            self.entries[PREFIX + "android/app/build.gradle.kts"],
        )
        for excluded in ("assets", "test", ".runtime", "tool"):
            self.assertFalse((self.destination / excluded).exists())
        self.assertEqual(result["status"], "SOURCES_PREPARED_NOT_BUILT")
        self.assertEqual(result["source_commit"], "unit-commit")
        self.assertEqual(len(result["files"]), 3)

    def test_manifest_changes_fail_before_writing(self):
        self.entries[PREFIX + "pubspec.yaml"] += b"    - assets/required.png\n"
        with self.assertRaisesRegex(ValueError, "Unexpected asset configuration"):
            prepare(archive(self.entries), self.destination, "unit")
        self.assertFalse(self.destination.exists())

    def test_existing_destination_is_never_overwritten(self):
        self.destination.mkdir()
        marker = self.destination / "keep.txt"
        marker.write_text("keep")
        with self.assertRaisesRegex(ValueError, "Destination exists"):
            prepare(archive(self.entries), self.destination, "unit")
        self.assertEqual(marker.read_text(), "keep")

    def test_unsafe_paths_and_private_source_resources_are_refused(self):
        for name in (
            "../outside",
            PREFIX + "lib/../outside",
            PREFIX + "lib/private.pem",
        ):
            with self.subTest(name=name):
                entries = {**self.entries, name: b"not copied"}
                with self.assertRaises(ValueError):
                    prepare(archive(entries), self.destination, "unit")
                self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
