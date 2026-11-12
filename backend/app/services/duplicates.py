from __future__ import annotations

import hashlib
import unicodedata


def normalize_text(value: str) -> str:
    return unicodedata.normalize("NFC", value.strip())


def compute_content_hash(title: str, description: str) -> str:
    canonical = f"{normalize_text(title)}\n{normalize_text(description)}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
