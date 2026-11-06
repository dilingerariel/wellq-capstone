"""The debt gate must reject new warnings and mandatory errors without sockets."""
import json
import subprocess
import sys

from integration.quality_gate import CONFIG, configuration_hash, evaluate, fingerprint


def issue(tmp_path, code="F401", row=1):
    path = tmp_path / "sample.py"
    if not path.exists():
        path.write_text("import os\n", encoding="utf-8")
    return {"filename": str(path), "code": code, "message": "Synthetic finding",
            "location": {"row": row, "column": 1}}


def test_reviewed_debt_is_visible_and_can_be_resolved(tmp_path):
    finding = issue(tmp_path)
    baseline = {"fingerprints": {fingerprint(finding, tmp_path): 1}}
    accepted = evaluate([finding], baseline, tmp_path)
    assert accepted["passed"] and accepted["remaining_reviewed_debt"] == 1
    resolved = evaluate([], baseline, tmp_path)
    assert resolved["passed"] and resolved["resolved_baseline_debt"] == 1


def test_policy_hash_is_portable_across_git_line_endings(tmp_path):
    first = tmp_path / "lf.toml"
    second = tmp_path / "crlf.toml"
    first.write_bytes(b'target-version = "py311"\npreview = false\n')
    second.write_bytes(b'target-version = "py311"\r\npreview = false\r\n')
    assert configuration_hash(first) == configuration_hash(second)


def test_new_debt_is_not_automatically_accepted(tmp_path):
    result = evaluate([issue(tmp_path)], {"fingerprints": {}}, tmp_path)
    assert not result["passed"] and result["new_debt"] == 1


def test_mandatory_error_cannot_be_exempted_by_baseline(tmp_path):
    finding = issue(tmp_path, "F821")
    baseline = {"fingerprints": {fingerprint(finding, tmp_path): 1}}
    result = evaluate([finding], baseline, tmp_path)
    assert not result["passed"] and result["mandatory_violations"] == 1


def test_an_extra_copy_of_a_warning_is_new_debt(tmp_path):
    finding = issue(tmp_path)
    baseline = {"fingerprints": {fingerprint(finding, tmp_path): 1}}
    result = evaluate([finding, finding], baseline, tmp_path)
    assert not result["passed"] and result["new_debt"] == 1


def test_fingerprint_survives_line_shift_but_rejects_changed_content(tmp_path):
    finding = issue(tmp_path)
    identity = fingerprint(finding, tmp_path)
    path = tmp_path / "sample.py"
    path.write_text("# shifted\nimport os\n", encoding="utf-8")
    finding["location"]["row"] = 2
    assert fingerprint(finding, tmp_path) == identity
    path.write_text("# shifted\nimport sys\n", encoding="utf-8")
    assert fingerprint(finding, tmp_path) != identity


def lint_defaults(source):
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--config", str(CONFIG), "--no-cache",
         "--stdin-filename", "synthetic.py", "--output-format=json", "-"],
        input=source, capture_output=True, text=True, check=False,
    )
    assert result.returncode in (0, 1)
    return json.loads(result.stdout)


def test_fastapi_depends_and_query_are_specific_exceptions():
    source = "from fastapi import Depends, Query\ndef endpoint(x=Depends(), y=Query()):\n    pass\n"
    assert not any(item["code"] == "B008" for item in lint_defaults(source))


def test_other_default_calls_and_shadowed_depends_still_fail():
    source = "def Depends():\n    return []\ndef endpoint(x=Depends()):\n    pass\n"
    assert any(item["code"] == "B008" for item in lint_defaults(source))


def test_fixture_registration_reexports_existing_functions():
    from integration import conftest as shared
    from integration.tests import conftest as provider

    assert shared.ctx is provider.ctx
    assert shared.raw is provider.raw
