import base64
import hashlib
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from services.models import now

MAX_BYTES = 5 * 1024 * 1024


def preserve_document(name, raw):
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Document must contain data and be at most 5 MB")
    name = Path(name).name
    suffix = Path(name).suffix.lower()
    if suffix not in (".txt", ".md", ".pdf"):
        raise ValueError("Use TXT, Markdown or a text PDF for this release")
    item = {
        "name": name,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "received": now(),
        "raw_base64": base64.b64encode(raw).decode(),
        "text": "",
        "extraction_note": "",
    }
    try:
        if suffix == ".pdf":
            reader = PdfReader(BytesIO(raw))
            if reader.is_encrypted:
                raise ValueError("Encrypted PDF cannot be read")
            if len(reader.pages) > 40:
                raise ValueError("PDF exceeds 40-page extraction limit")
            text = "\n".join(f"Page {i + 1}\n{p.extract_text()}" for i, p in enumerate(reader.pages))
        else:
            text = raw.decode("utf-8-sig")
        item["text"] = text[:30000]
        item["extraction_note"] = (
            "Text limited to 30,000 characters"
            if len(text) > 30000
            else "Text extraction only; officer review required"
        )
        if not text.strip():
            item["extraction_note"] = "No usable text; scanned PDFs need OCR outside this release"
    except Exception:
        item["extraction_note"] = (
            "Extraction failed; original preserved. Use a text document or enter a summary."
        )
    return item
