"""Invented synthetic secrets only; no Docker, identity, Mongo or network."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import pytest
from integration.publication import REDACTED, PublicExportRefused, sanitize, write_public
from integration.scan_publication import scan


@pytest.mark.parametrize("name", ["PASSWORD", "nestedPassword", "apiKey", "private-key", "access_token",
    "JWT_SECRET", "SIGNING_KEY", "AUTHORIZATION", "credentials", "DATABASE_URL", "MONGODB_URI", "DB_PASS", "connectionString"])
def test_nested_compose_extensions_and_sensitive_names(name):
    source = {"x-env": {name: "invented-test-value"}, "x-app": {"environment": {name: "invented-test-value"}},
              "services": {"api": {"environment": {name: "invented-test-value", "ENVIRONMENT": "test"}}}}
    original = copy.deepcopy(source)
    clean = sanitize(source)
    assert "invented-test-value" not in json.dumps(clean)
    assert clean["x-env"][name] == REDACTED
    assert clean["services"]["api"]["environment"]["ENVIRONMENT"] == "test"
    assert source == original


@pytest.mark.parametrize("uri", ["mongodb://synthetic-user:invented-pass@mongo.invalid/test",
    "postgresql://user:encoded%40pass@db.invalid/test", "https://objects.invalid/test?signature=" + "a" * 32])
def test_authenticated_and_signed_uri_under_unexpected_field(uri):
    assert sanitize({"message": "prefix " + uri + " suffix"}) == {"message": "prefix " + REDACTED + " suffix"}


def test_unrelated_template_does_not_hide_an_authenticated_uri():
    uri = "mongodb://" + "user:invented-pass@db.invalid/test?unused=${VARIABLE}"
    assert sanitize({"message": uri}) == {"message": REDACTED}


def test_mixed_lists_empty_values_and_public_fields():
    source = {"list": [{"api_key": "invented"}, [1, False, None, ""], "public"],
              "secret": {"nested": ["invented", None, ""]}, "password": "", "token": None,
              "image": "mongo:7.0", "name": "analítica", "size": 7, "public_url": "https://example.invalid/docs"}
    clean = sanitize(source)
    assert clean["list"] == [{"api_key": REDACTED}, [1, False, None, ""], "public"]
    assert clean["secret"] == {"nested": [REDACTED, None, ""]}
    assert clean["password"] == "" and clean["token"] is None
    assert json.loads(json.dumps(clean)) == clean and clean["name"] == source["name"]


def test_known_secret_is_removed_under_unexpected_name():
    secret = "invented-only-for-this-test"
    assert sanitize({"unexpected": "prefix " + secret}, (secret,)) == {"unexpected": "prefix " + REDACTED}


@pytest.mark.parametrize("value", ["PASSWORD=invented", "API_KEY='invented with spaces'", "--password invented"])
def test_secret_environment_lists_and_command_options(value):
    cleaned = sanitize({"environment": [value, "ENVIRONMENT=test"]})
    assert "invented" not in json.dumps(cleaned) and cleaned["environment"][1] == "ENVIRONMENT=test"


@pytest.mark.parametrize("kind", ["object", "cycle", "deep", "nonstring-key", "nan", "secret-key"])
def test_refusal_without_echo_or_public_file(tmp_path, kind):
    secret = "invented-only-for-this-test"
    value = {"safe": object()}
    if kind == "cycle":
        value = []; value.append(value)
    elif kind == "deep":
        value = "safe"
        for _ in range(70): value = [value]
    elif kind == "nonstring-key": value = {1: "value"}
    elif kind == "nan": value = float("nan")
    elif kind == "secret-key": value = {secret: "value"}
    target = tmp_path / "evidence-public.json"
    with pytest.raises(PublicExportRefused) as error:
        write_public(value, target, (secret,))
    assert secret not in str(error.value) and not target.exists()


def test_private_key_and_bearer_material_are_redacted():
    private = "-----BEGIN " + "PRIVATE KEY-----\ninvented\n-----END " + "PRIVATE KEY-----"
    assert sanitize({"message": private})["message"] == REDACTED
    assert sanitize({"message": "Bearer " + "invented-token-value"})["message"] == REDACTED


def test_public_write_keeps_original_and_refuses_accidental_overwrite(tmp_path):
    original = tmp_path / "historical.json";original.write_text('{"password":"invented"}')
    target = tmp_path / "historical-public.json"
    write_public(json.loads(original.read_text()), target)
    assert original.read_text() == '{"password":"invented"}'
    assert json.loads(target.read_text())["password"] == REDACTED
    with pytest.raises(PublicExportRefused): write_public({}, original)
    with pytest.raises(PublicExportRefused): write_public({}, original, replace=True)


def test_cli_refusal_does_not_echo_bad_json_or_overwrite_source(tmp_path):
    script = Path(__file__).with_name("publication.py")
    source = tmp_path / "input.json";source.write_text('{"password":"invented-test-credential"')
    target = tmp_path / "output-public.json"
    result = subprocess.run([sys.executable, str(script), "--input", str(source), "--output", str(target)],capture_output=True,text=True)
    assert result.returncode == 1 and "invented-test-credential" not in result.stdout + result.stderr
    assert not target.exists()
    result = subprocess.run([sys.executable, str(script), "--input", str(source), "--output", str(source)],capture_output=True,text=True)
    assert result.returncode == 1 and "invented-test-credential" in source.read_text()


def test_scanner_fails_for_effective_secret_even_in_redacted_filename(tmp_path):
    name = "already-redacted.json";secret = "invented-scanner-negative"
    (tmp_path / name).write_text(json.dumps({"unknown": secret}))
    findings, _ = scan(tmp_path, [name], (secret,))
    assert findings == [{"path": name, "category": "effective_secret", "count": 1}]
    assert secret not in json.dumps(findings)


def test_scanner_fixture_policy_never_exempts_effective_secrets(tmp_path):
    name = "backend/integration/test_publication.py";path = tmp_path / name;path.parent.mkdir(parents=True)
    secret = "invented-known-negative"
    path.write_text('value = "mongodb://user:' + secret + '@test.invalid/db"')
    findings, _ = scan(tmp_path, [name], (secret,))
    assert any(x["category"] == "effective_secret" for x in findings)


def test_scanner_does_not_allow_unreviewed_fixture_domains(tmp_path):
    name = "backend/integration/test_publication.py";path = tmp_path / name;path.parent.mkdir(parents=True)
    path.write_text('value = "mongodb://' + 'user:invented@unapproved.example/db"')
    findings, _ = scan(tmp_path, [name], ())
    assert any(x["category"] == "authenticated_or_signed_uri" for x in findings)


def test_powershell_public_export_covers_extensions_and_preserves_original(tmp_path):
    common = Path(__file__).with_name("Common.ps1")
    original = tmp_path / "compose-redacted.json";original.write_text("historical-original")
    env = tmp_path / "synthetic.env";env.write_text("TEST_PASSWORD=invented-env-secret\n")
    command = ". '" + str(common) + "'; $config = $input | Out-String | ConvertFrom-Json; Export-IntegrationPublicEvidence -Config $config -OutputFile '" + str(original) + "' -SecretsEnvFile '" + str(env) + "'"
    result = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        input=json.dumps({"name": "analítica", "x-env": {"PASSWORD": "invented-env-secret"}, "x-app": {"environment": {"MONGODB_URI": "mongodb://test:invented-pass@mongo.invalid/db"}}}),capture_output=True,text=True)
    assert result.returncode == 0, "PowerShell export failed (input withheld)"
    assert original.read_text() == "historical-original"
    public = json.loads((tmp_path / "compose-public.json").read_text(encoding="utf-8-sig"))
    assert public["x-env"]["PASSWORD"] == REDACTED
    assert public["x-app"]["environment"]["MONGODB_URI"] == REDACTED
    assert public["name"] == "analítica"
