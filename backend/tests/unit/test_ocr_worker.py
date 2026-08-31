from __future__ import annotations

from pathlib import Path

import pikepdf
import pytest
from app.core.config import settings
from app.infrastructure.ocr_worker import (
    PermanentOcrError,
    _validate_output,
    inspect_pdf,
)


def write_pdf(path: Path, *, pages: int = 1, signed: bool = False) -> None:
    with pikepdf.Pdf.new() as pdf:
        for _index in range(pages):
            pdf.add_blank_page(page_size=(72, 72))
        if signed:
            signature = pikepdf.Dictionary(FT=pikepdf.Name.Sig)
            pdf.Root.AcroForm = pikepdf.Dictionary(Fields=pikepdf.Array([signature]))
        pdf.save(path)


def test_accepts_valid_unsigned_pdf(tmp_path: Path) -> None:
    path = tmp_path / "valid.pdf"
    write_pdf(path)

    inspect_pdf(path)


def test_rejects_encrypted_pdf(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    with pikepdf.Pdf.new() as pdf:
        pdf.add_blank_page(page_size=(72, 72))
        pdf.save(path, encryption=pikepdf.Encryption(owner="owner", user="user"))

    with pytest.raises(PermanentOcrError) as rejected:
        inspect_pdf(path)
    assert rejected.value.code == "ocr_encrypted_pdf"


def test_rejects_digitally_signed_pdf(tmp_path: Path) -> None:
    path = tmp_path / "signed.pdf"
    write_pdf(path, signed=True)

    with pytest.raises(PermanentOcrError) as rejected:
        inspect_pdf(path)
    assert rejected.value.code == "ocr_signed_pdf"


def test_rejects_pdf_over_page_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "long.pdf"
    write_pdf(path, pages=2)
    monkeypatch.setattr(settings, "OCR_MAX_PAGES", 1)

    with pytest.raises(PermanentOcrError) as rejected:
        inspect_pdf(path)
    assert rejected.value.code == "ocr_page_limit_exceeded"


def test_validates_generated_pdf_header_and_size(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    valid = tmp_path / "output.pdf"
    write_pdf(valid)
    assert _validate_output(valid) == valid.stat().st_size

    invalid = tmp_path / "invalid.pdf"
    invalid.write_bytes(b"not a pdf")
    with pytest.raises(PermanentOcrError) as rejected:
        _validate_output(invalid)
    assert rejected.value.code == "ocr_output_invalid"

    monkeypatch.setattr(settings, "OCR_MAX_OUTPUT_BYTES", valid.stat().st_size - 1)
    with pytest.raises(PermanentOcrError) as too_large:
        _validate_output(valid)
    assert too_large.value.code == "ocr_output_too_large"
