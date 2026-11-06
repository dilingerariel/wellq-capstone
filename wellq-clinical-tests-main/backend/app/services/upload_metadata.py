"""Declared metadata policy; actual bytes remain verified by the worker."""
import unicodedata
from fastapi import HTTPException

EXTENSIONS = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg",
              "png": "image/png", "heic": "image/heic"}
DANGEROUS_EXTENSIONS = frozenset(("exe", "com", "bat", "cmd", "ps1", "vbs", "js", "msi", "scr", "dll", "hta", "sh"))


def normalize_filename(value):
    value = unicodedata.normalize("NFC", value)
    if (any(c in '/\\:<>"|?*' or unicodedata.category(c) == "Cc" or
            c in '\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069' for c in value)
            or value.endswith((".", " "))):
        raise ValueError("Unsafe file name")
    parts = value.lower().split(".")
    if len(parts) < 2 or not any(parts[:-1]) or parts[-1] not in EXTENSIONS:
        raise ValueError("Unsupported file extension")
    if any(part in DANGEROUS_EXTENSIONS for part in parts[1:-1]):
        raise ValueError("Unsafe double extension")
    return value


def validate_metadata(request):
    if EXTENSIONS[request.file_name.rsplit(".", 1)[-1].lower()] != request.mime_type:
        raise HTTPException(422, detail={"code": "INVALID_METADATA", "message": "File extension and MIME disagree"})
