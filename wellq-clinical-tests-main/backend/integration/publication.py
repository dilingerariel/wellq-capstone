"""Standard-library public evidence boundary. Never logs input or secret values."""
import argparse
import json
import math
import os
from pathlib import Path
import re
import sys
import tempfile

REDACTED = "<REDACTED>"
SENSITIVE = re.compile(r"PASSWORD|PASSWD|(?:^|_)(?:PWD|PASS)(?:_|$)|TOKEN|SECRET|PRIVATE_?KEY|API_?KEY|ACCESS_?KEY|CREDENTIAL|AUTHORIZATION|SIGNING_?KEY|MONGODB_URI|DATABASE_URL|CONNECTION_?STRING|(?:^|_)DSN(?:_|$)", re.I)
PRIVATE = re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")
JWT = re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}")
URI = re.compile(r"[a-z][a-z0-9+.-]*://[^\s\x22\x27<>]+", re.I)
AUTH = re.compile(r"(?:Bearer|Basic)\s+[A-Za-z0-9_+/=.-]{8,}", re.I)
QUERY = re.compile(r"[?&](?:token|api[_-]?key|password|signature|X-Goog-Signature|X-Amz-Signature)=", re.I)
PROVIDER = re.compile(r"(?:ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{24,})")
ASSIGNMENT = re.compile(r"([A-Za-z_][A-Za-z0-9_.-]*)\s*=\s*(\x22[^\x22]*\x22|\x27[^\x27]*\x27|[^\s;\x22\x27,\]\}]+)")
SECRET_OPTION = re.compile(r"(--(?:password|passwd|token|api-key|private-key|signing-key|secret))(?:=|\s+)([^\s]+)", re.I)


class PublicExportRefused(ValueError):
    """Fixed message only: callers must never reflect the source exception."""


def sensitive_name(name):
    normalized = re.sub(r"([a-z])([A-Z])", r"\1_\2", name).replace("-", "_")
    return bool(SENSITIVE.search(normalized))


def known_secrets(env_file):
    if env_file is None:
        return ()
    values = []
    for line in Path(env_file).read_text(encoding="utf-8-sig").splitlines():
        if not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            value = value.strip().strip("\x22\x27")
            if sensitive_name(key) and len(value) >= 8 and "${" not in value:
                values.append(value)
    return tuple(values)


def unsafe_uri(value):
    # Userinfo in authenticated URLs; templates and explicit redaction are safe.
    authority = value.split("://", 1)[-1].split("/", 1)[0]
    authenticated = False
    if "@" in authority and ":" in authority.rsplit("@", 1)[0]:
        password = authority.rsplit("@", 1)[0].split(":", 1)[1]
        template = re.fullmatch(r"\$?\{[A-Za-z_][A-Za-z0-9_.]*\}", password)
        authenticated = bool(password) and not template and password != REDACTED
    return authenticated or bool(QUERY.search(value))


def text_categories(value, secrets=()):
    found = []
    if any(secret and secret in value for secret in secrets):
        found.append("effective_secret")
    for name, pattern in (("private_key", PRIVATE), ("jwt_literal", JWT),
                          ("authorization", AUTH), ("provider_token", PROVIDER)):
        if pattern.search(value):
            found.append(name)
    if any(unsafe_uri(m.group()) for m in URI.finditer(value)):
        found.append("authenticated_or_signed_uri")
    if any(sensitive_name(m.group(1)) and m.group(2) != REDACTED for m in ASSIGNMENT.finditer(value)):
        found.append("sensitive_assignment")
    return found


def sanitize(data, secrets=()):
    active = set()

    def visit(value, depth=0):
        if depth > 64:
            raise PublicExportRefused("Public export refused")
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                raise PublicExportRefused("Public export refused")
            return value
        if isinstance(value, str):
            if PRIVATE.search(value):
                return REDACTED
            for secret in secrets:
                if secret:
                    value = value.replace(secret, REDACTED)
            value = URI.sub(lambda m: REDACTED if unsafe_uri(m.group()) else m.group(), value)
            for pattern in (JWT, AUTH, PROVIDER):
                value = pattern.sub(REDACTED, value)
            value = ASSIGNMENT.sub(lambda m: m.group(1) + "=" + REDACTED if sensitive_name(m.group(1)) else m.group(), value)
            value = SECRET_OPTION.sub(lambda m: m.group(1) + "=" + REDACTED, value)
            return value
        if not isinstance(value, (dict, list)) or id(value) in active:
            raise PublicExportRefused("Public export refused")
        active.add(id(value))
        try:
            if isinstance(value, list):
                return [visit(item, depth + 1) for item in value]
            result = {}
            for key, item in value.items():
                if not isinstance(key, str) or text_categories(key, secrets):
                    raise PublicExportRefused("Public export refused")
                if sensitive_name(key) and item not in (None, ""):
                    # Preserve container shape; redact every leaf of secret maps/lists.
                    result[key] = redact_leaves(item, depth + 1)
                else:
                    result[key] = visit(item, depth + 1)
            return result
        finally:
            active.remove(id(value))

    def redact_leaves(value, depth):
        if depth > 64 or (isinstance(value, (dict, list)) and id(value) in active):
            raise PublicExportRefused("Public export refused")
        if isinstance(value, dict):
            active.add(id(value))
            try:
                result = {}
                for key, item in value.items():
                    if not isinstance(key, str) or text_categories(key, secrets):
                        raise PublicExportRefused("Public export refused")
                    result[key] = redact_leaves(item, depth + 1)
                return result
            finally:
                active.remove(id(value))
        if isinstance(value, list):
            active.add(id(value))
            try:
                return [redact_leaves(item, depth + 1) for item in value]
            finally:
                active.remove(id(value))
        if value is None or value == "":
            return value
        if not isinstance(value, (str, int, float, bool)):
            raise PublicExportRefused("Public export refused")
        return REDACTED

    cleaned = visit(data)
    encoded = json.dumps(cleaned, ensure_ascii=False, allow_nan=False)
    if text_categories(encoded, secrets):
        raise PublicExportRefused("Public export refused")
    return cleaned


def write_public(data, target, secrets=(), replace=False):
    cleaned = sanitize(data, secrets)
    content = json.dumps(cleaned, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    target = Path(target)
    if replace and not target.name.endswith(("-public.json", ".public.json")):
        raise PublicExportRefused("Public export refused")
    if target.exists() and not replace:
        raise PublicExportRefused("Public export refused")
    # Only sanitized content reaches disk. The original is never a temp file.
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent,
                                     suffix=".public.tmp", delete=False) as stream:
        temp = Path(stream.name)
        stream.write(content)
    try:
        if replace:
            os.replace(temp, target)
        else:
            # Exclusive final creation avoids overwriting a concurrent writer.
            with target.open("x", encoding="utf-8") as stream:
                stream.write(content)
    finally:
        temp.unlink(missing_ok=True)
    return cleaned


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input")
    parser.add_argument("--stdin", action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--known-secrets-env")
    parser.add_argument("--replace-public", action="store_true")
    args = parser.parse_args()
    try:
        if bool(args.input) == bool(args.stdin):
            raise PublicExportRefused("Public export refused")
        if args.input and Path(args.input).resolve() == Path(args.output).resolve():
            raise PublicExportRefused("Public export refused")
        source = Path(args.input).read_text(encoding="utf-8-sig") if args.input else sys.stdin.buffer.read().decode("utf-8-sig")
        data = json.loads(source)
        write_public(data, args.output, known_secrets(args.known_secrets_env), args.replace_public)
    except Exception:
        print("Public export refused; inspect structure and policy without logging input", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
