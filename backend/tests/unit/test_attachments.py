from __future__ import annotations

import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.core.errors import AppError
from app.services.attachments import MAX_FILE_SIZE, cleanup_staged, stage_files

PNG = b"\x89PNG\r\n\x1a\n" + b"contenido"


def upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(filename=filename, file=BytesIO(content))


def test_stages_valid_png(tmp_path: Path) -> None:
    staged = asyncio.run(stage_files([upload("foto.png", PNG)], tmp_path))
    try:
        assert len(staged) == 1
        assert staged[0].mime_type == "image/png"
        assert staged[0].size_bytes == len(PNG)
        assert staged[0].temp_path.exists()
    finally:
        cleanup_staged(staged)


def test_rejects_unknown_extension(tmp_path: Path) -> None:
    with pytest.raises(AppError) as error:
        asyncio.run(stage_files([upload("notas.txt", b"hola")], tmp_path))
    assert error.value.code == "invalid_attachment"


def test_rejects_content_not_matching_signature(tmp_path: Path) -> None:
    with pytest.raises(AppError) as error:
        asyncio.run(stage_files([upload("foto.png", b"no es una imagen")], tmp_path))
    assert error.value.code == "invalid_attachment"


def test_rejects_empty_file(tmp_path: Path) -> None:
    with pytest.raises(AppError) as error:
        asyncio.run(stage_files([upload("foto.png", b"")], tmp_path))
    assert error.value.code == "attachment_empty"


def test_rejects_too_many_files(tmp_path: Path) -> None:
    files = [upload(f"foto{i}.png", PNG) for i in range(6)]
    with pytest.raises(AppError) as error:
        asyncio.run(stage_files(files, tmp_path))
    assert error.value.code == "too_many_attachments"


def test_rejects_too_large_file(tmp_path: Path) -> None:
    with pytest.raises(AppError) as error:
        asyncio.run(stage_files([upload("foto.png", PNG + b"0" * MAX_FILE_SIZE)], tmp_path))
    assert error.value.code == "attachment_too_large"
