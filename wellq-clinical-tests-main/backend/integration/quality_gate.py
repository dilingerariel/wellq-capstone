"""Ruff gate: mandatory correctness and an explicit, non-growing debt inventory."""
import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
CONFIG = BACKEND / "ruff.toml"
BASELINE = BACKEND / "docs/evidencias_ruff/debt-baseline.json"
# Each remaining site is reviewed and fingerprinted. All other rules are fatal.
DEBT_RULES = frozenset({
    "I001", "UP045", "DTZ003", "BLE001", "UP035", "F401", "TRY004", "UP006",
    "F841", "PIE804", "UP017", "SIM117", "RUF059", "FURB167", "PLW1510",
    "RUF100", "SIM115",
})


def configuration_hash(path=CONFIG):
    # Git may check the same TOML out with LF or CRLF on different runners.
    content = Path(path).read_text(encoding="utf-8-sig")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def fingerprint(issue, backend=BACKEND):
    path = Path(issue["filename"]).resolve()
    relative = path.relative_to(backend).as_posix()
    line = path.read_text(encoding="utf-8-sig").splitlines()[issue["location"]["row"] - 1].strip()
    # Never store source lines: they might contain clinical literals or credentials.
    identity = json.dumps([relative, issue["code"], issue["message"], line], ensure_ascii=True)
    return hashlib.sha256(identity.encode()).hexdigest()


def evaluate(issues, baseline, backend=BACKEND):
    mandatory = [issue for issue in issues if issue["code"] not in DEBT_RULES]
    debt = [issue for issue in issues if issue["code"] in DEBT_RULES]
    current = Counter(fingerprint(issue, backend) for issue in debt)
    allowed = Counter(baseline.get("fingerprints", {}))
    additions = current - allowed
    resolved = allowed - current
    return {
        "passed": not mandatory and not additions,
        "ruff_observations": len(issues),
        "mandatory_violations": len(mandatory),
        "new_debt": sum(additions.values()),
        "remaining_reviewed_debt": len(debt),
        "resolved_baseline_debt": sum(resolved.values()),
        "note": "Passing this gate does not mean raw Ruff or every possible Ruff rule passes.",
    }


def run_ruff():
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(CONFIG),
         "--no-cache", "--output-format=json", str(BACKEND)],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
    if result.returncode not in (0, 1):
        raise RuntimeError("Ruff configuration or execution failed")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report")
    args = parser.parse_args()
    issues = run_ruff()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    if baseline.get("ruff_version") != "0.17.3" or baseline.get("policy_version") != 1:
        raise RuntimeError("Unreviewed debt policy version")
    if baseline.get("configuration_sha256") != configuration_hash():
        raise RuntimeError("Ruff policy changed without debt review")
    report = evaluate(issues, baseline)
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, IndexError, subprocess.SubprocessError):
        # A failed/missing inventory is never treated as a green gate.
        print("Quality gate unavailable; no approval", file=sys.stderr)
        raise SystemExit(2)
