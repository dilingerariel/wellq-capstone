"""Read-only selection scanner; reports paths/categories/counts, never values."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from integration.publication import URI, known_secrets, text_categories, unsafe_uri


PRIVATE_EVIDENCE = (
    "docs/evidencias_integracion/compose-resolved-redacted.json",
    "docs/evidencias_s01_s02/compose-resolved-redacted.json",
    "docs/evidencias_s01_s02/compose-at-stop-redacted.json",
    "docs/evidencias_g03_g06/compose-resolved-redacted.json",
    "docs/evidencias_g03_g06/compose-at-stop-redacted.json",
)


def candidates(root):
    changed = subprocess.check_output(["git", "diff", "--name-only", "HEAD", "-z"], cwd=root).decode().split("\0")
    new = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "-z"], cwd=root).decode().split("\0")
    return sorted({name for name in changed + new if name and (root / name).is_file()})


def advisory_examples(path, data):
    # Narrow exception: public exploit text in the historical vulnerability report.
    # Effective local secrets are still scanned even within this field.
    if path.name != "dependencies-before.json" or not isinstance(data, dict):
        return ()
    return tuple(vuln["description"] for dep in data.get("dependencies", []) for vuln in dep.get("vulns", [])
                 if isinstance(vuln.get("description"), str))


def scan(root, paths, secrets):
    findings = []
    examples = []
    for name in paths:
        path = root / name
        content = path.read_bytes()
        try:
            text = content.decode("utf-8-sig")
        except UnicodeError:
            findings.append({"path": name, "category": "unreviewed_binary", "count": 1})
            continue
        try:
            public_examples = advisory_examples(path, json.loads(text))
        except (ValueError, TypeError, KeyError):
            public_examples = ()
        counts = Counter(text_categories(text, secrets))
        if path.suffix != ".json":
            # Source examples/regex/tests are not exported runtime assignment data.
            # Effective known secrets, private material and authenticated URLs still fail.
            counts.pop("sensitive_assignment", None)
        # Count known-secret occurrences separately, without exposing the match.
        if counts.get("effective_secret"):
            counts["effective_secret"] = sum(text.count(value) for value in secrets if value)
        if public_examples:
            parsed = json.loads(text)
            for dep in parsed.get("dependencies", []):
                for vuln in dep.get("vulns", []):
                    vuln.pop("description", None)
            outside_advisory = text_categories(json.dumps(parsed), secrets)
            for category in ("jwt_literal", "sensitive_assignment"):
                if counts.get(category) and category not in outside_advisory:
                    counts.pop(category)
                    examples.append({"path": name, "category": "public_advisory_" + category, "count": 1})
        fixture = (name.endswith("/integration/test_publication.py") or
                   ("/docs/evidencias_publicacion/sanitizer-" in name and name.endswith(".xml")))
        if fixture and counts.get("authenticated_or_signed_uri"):
            urls = [m.group() for m in URI.finditer(text) if unsafe_uri(m.group())]
            if urls and all((urlsplit(url).hostname or "").endswith(".invalid") for url in urls):
                counts.pop("authenticated_or_signed_uri")
                examples.append({"path": name, "category": "invented_fixture_reserved_invalid_domain", "count": len(urls)})
        for category, count in counts.items():
            findings.append({"path": name, "category": category, "count": count})
    return findings, examples


def group(path):
    relative = path.removeprefix("wellq-clinical-tests-main/backend/")
    if relative.startswith("app/"):
        return "production"
    if relative.startswith(("checks/", "tests/")):
        return "tests"
    if relative.startswith(("integration/", "scripts/")):
        return "scripts_and_integration"
    if relative.startswith("docs/"):
        return "public_evidence" if relative.endswith("-public.json") else "documentation_and_reviewed_evidence"
    return "public_configuration"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-private-evidence", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    backend = root / "wellq-clinical-tests-main/backend"
    paths = candidates(root)
    if args.include_private_evidence:
        paths = sorted(set(paths) | {"wellq-clinical-tests-main/backend/" + name for name in PRIVATE_EVIDENCE})
    secrets = known_secrets(backend / "integration/.runtime/integration.env")
    findings, examples = scan(root, paths, secrets)
    report = {"scope": "changed tracked and relevant untracked files; not a full-history clearance",
              "files_scanned": len(paths), "effective_secret_findings": sum(x["count"] for x in findings if x["category"] == "effective_secret"),
              "blocking_findings": findings, "reviewed_public_examples": examples, "passed": not findings}
    if args.write_report:
        # Never export a permit list for a failing selection.
        if findings or args.include_private_evidence:
            print(json.dumps(report, ensure_ascii=True))
            return 1
        destination = backend / "docs/evidencias_publicacion"
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "secret-scan.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        allowlist = {"warning": "Proposal only. No staging performed. Rerun after every change.",
                     "files": [{"path": name, "category": group(name)} for name in paths],
                     "excluded_private_originals": list(PRIVATE_EVIDENCE)}
        (destination / "allowlist.json").write_text(json.dumps(allowlist, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True))
    return 1 if findings else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("Publication scan refused; no selection exported", file=sys.stderr)
        raise SystemExit(1)
