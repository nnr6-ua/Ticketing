"""Validación, almacenamiento temporal y movimiento de adjuntos."""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.errors import ApiError

MAX_FILES = 5
MAX_FILE_SIZE = 5 * 1024 * 1024

ALLOWED_TYPES: dict[str, tuple[str, tuple[bytes, ...]]] = {
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".gif": ("image/gif", (b"GIF87a", b"GIF89a")),
}


@dataclass
class StagedFile:
    temp_path: Path
    stored_filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    sha256: str


def _validate_upload(upload: UploadFile) -> tuple[str, str, tuple[bytes, ...]]:
    original = Path(upload.filename or "").name.strip()
    if not original:
        raise ApiError(400, "attachment_name_required", "El adjunto no tiene nombre.")

    suffix = Path(original).suffix.lower()
    if suffix not in ALLOWED_TYPES:
        raise ApiError(
            422,
            "invalid_attachment",
            "Solo se permiten imágenes PNG, JPG o GIF.",
        )

    mime_type, signatures = ALLOWED_TYPES[suffix]
    return original, mime_type, signatures


async def stage_files(files: list[UploadFile], temp_dir: Path) -> list[StagedFile]:
    if not files:
        return []
    if len(files) > MAX_FILES:
        raise ApiError(
            422,
            "too_many_attachments",
            f"Puedes adjuntar como máximo {MAX_FILES} archivos.",
        )

    staged: list[StagedFile] = []
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        for upload in files:
            original, mime_type, signatures = _validate_upload(upload)
            content = await upload.read()
            size = len(content)

            if size == 0:
                raise ApiError(
                    422, "attachment_empty", "El adjunto está vacío."
                )
            if size > MAX_FILE_SIZE:
                raise ApiError(
                    422,
                    "attachment_too_large",
                    "Cada adjunto puede pesar como máximo 5 MB.",
                )
            if not any(content.startswith(signature) for signature in signatures):
                raise ApiError(
                    422,
                    "invalid_attachment",
                    "El contenido del archivo no coincide con una imagen PNG, JPG o GIF.",
                )

            stored_filename = f"{uuid4().hex}{Path(original).suffix.lower()}"
            temp_path = temp_dir / stored_filename
            temp_path.write_bytes(content)
            staged.append(
                StagedFile(
                    temp_path=temp_path,
                    stored_filename=stored_filename,
                    original_filename=original,
                    mime_type=mime_type,
                    size_bytes=size,
                    sha256=hashlib.sha256(content).hexdigest(),
                )
            )
    except Exception:
        cleanup_staged(staged)
        raise

    return staged


def move_staged(
    staged: list[StagedFile], attachments_dir: Path, ticket_number: str
) -> list[tuple[StagedFile, str]]:
    if not staged:
        return []

    relative_dir = Path(ticket_number)
    target_dir = attachments_dir / relative_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    moved: list[tuple[StagedFile, str]] = []
    try:
        for item in staged:
            target = target_dir / item.stored_filename
            shutil.move(str(item.temp_path), str(target))
            moved.append((item, str(relative_dir / item.stored_filename)))
    except Exception:
        remove_files([str(attachments_dir / relative) for _, relative in moved])
        raise

    return moved


def remove_files(paths: list[str]) -> None:
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            continue


def cleanup_staged(staged: list[StagedFile]) -> None:
    remove_files([str(item.temp_path) for item in staged])
