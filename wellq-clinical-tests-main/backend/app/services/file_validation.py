"""Content checks plus ClamAV; never approves without a scanner."""
import hashlib
import io
import socket
import struct
from app.config import settings

class FileRejected(ValueError):
    pass
class ScannerUnavailable(RuntimeError):
    pass

def detect_mime(data):
    if data.startswith(b"%PDF-"): return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"): return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "image/png"
    if len(data) >= 12 and data[4:8] == b"ftyp" and any(b in data[8:40] for b in (b"heic", b"heix", b"hevc", b"hevx", b"mif1")):
        return "image/heic"
    raise FileRejected("CONTENT_INVALID")

def validate_document(data, declared_mime, size_bytes, sha256):
    if not data or len(data) > settings.MAX_CLINICAL_FILE_BYTES: raise FileRejected("SIZE_REJECTED")
    if len(data) != size_bytes or hashlib.sha256(data).hexdigest() != sha256: raise FileRejected("OBJECT_MISMATCH")
    mime = detect_mime(data)
    if mime != declared_mime or mime not in settings.ALLOWED_MIME_TYPES: raise FileRejected("MIME_MISMATCH")
    try:
        if mime == "application/pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= settings.MAX_DOCUMENT_PAGES: raise ValueError()
            for page in reader.pages:
                if float(page.mediabox.width) <= 0 or float(page.mediabox.height) <= 0: raise ValueError()
        else:
            from PIL import Image
            if mime == "image/heic":
                from pillow_heif import register_heif_opener
                register_heif_opener()
            image = Image.open(io.BytesIO(data))
            if not 0 < image.width * image.height <= settings.MAX_IMAGE_PIXELS: raise ValueError()
            image.load()
    except Exception:
        raise FileRejected("DOCUMENT_CORRUPT")
    return mime

class ClamAVScanner:
    def scan(self, data):
        if not settings.CLAMAV_HOST: raise ScannerUnavailable("Scanner not configured")
        try:
            with socket.create_connection((settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=settings.MALWARE_SCAN_TIMEOUT_SECONDS) as c:
                c.sendall(b"zINSTREAM\0")
                for i in range(0, len(data), 65536):
                    chunk = data[i:i+65536]; c.sendall(struct.pack("!I", len(chunk)) + chunk)
                c.sendall(struct.pack("!I", 0)); result = b""
                while b"\0" not in result and len(result) < 4096:
                    part = c.recv(4096)
                    if not part: break
                    result += part
            if result == b"stream: OK\0": return
            if b"FOUND" in result: raise FileRejected("MALWARE_DETECTED")
            raise ScannerUnavailable("Scanner did not approve")
        except (OSError, TimeoutError):
            raise ScannerUnavailable("Scanner unavailable")

    def scan_document(self, data, mime_type):
        """Scan the uploaded bytes and separately scan PDF attachments.

        ClamAV does not reliably recurse into embedded PDF files. Scanning each
        attachment prevents a clean-looking PDF wrapper from hiding malware.
        The total extracted attachment size is bounded by the upload limit.
        """
        self.scan(data)
        if mime_type != "application/pdf":
            return
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data), strict=True)
            total = 0
            for attachments in reader.attachments.values():
                for attachment in attachments:
                    if not isinstance(attachment, bytes):
                        raise FileRejected("DOCUMENT_CORRUPT")
                    total += len(attachment)
                    if total > settings.MAX_CLINICAL_FILE_BYTES:
                        raise FileRejected("SIZE_REJECTED")
                    self.scan(attachment)
        except (FileRejected, ScannerUnavailable):
            raise
        except Exception:
            # A document whose attachments cannot be enumerated is not safe to
            # promote, even if the outer PDF itself passed MIME validation.
            raise FileRejected("DOCUMENT_CORRUPT") from None

scanner = ClamAVScanner()
