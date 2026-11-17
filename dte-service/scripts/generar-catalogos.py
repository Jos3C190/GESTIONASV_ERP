#!/usr/bin/env python3
"""Regenera catalogos.json desde el Excel oficial de Hacienda, sin dependencias externas."""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CATALOG_RE = re.compile(r"^(CAT-\d{3})\s+(.+)$")
EXPECTED_IDS = [f"CAT-{number:03d}" for number in range(1, 34)]
REPEATED_CODE_CATALOGS = {"CAT-008", "CAT-013", "CAT-015"}
HEADER_NAMES = {"codigo", "código"}


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(f".//{{{MAIN_NS}}}t"))

    value = cell.find(f"{{{MAIN_NS}}}v")
    raw = "" if value is None or value.text is None else value.text
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError) as error:
            raise ValueError(f"Índice shared string inválido: {raw!r}") from error
    return raw


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in archive.namelist():
        return []
    root = ET.fromstring(archive.read(path))
    return ["".join(node.text or "" for node in item.findall(f".//{{{MAIN_NS}}}t")) for item in root]


def _first_worksheet_path(archive: zipfile.ZipFile) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    first_sheet = workbook.find(f".//{{{MAIN_NS}}}sheet")
    if first_sheet is None:
        raise ValueError("El Excel no contiene hojas")
    relationship_id = first_sheet.get(f"{{{REL_NS}}}id")

    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relationship in relationships.findall(f"{{{PKG_REL_NS}}}Relationship"):
        if relationship.get("Id") == relationship_id:
            target = relationship.get("Target") or ""
            if target.startswith("/"):
                return target.lstrip("/")
            return posixpath.normpath(posixpath.join("xl", target))
    raise ValueError("No se encontró la relación de la primera hoja")


def _rows_from_xlsx(source: Path):
    with zipfile.ZipFile(source) as archive:
        strings = _shared_strings(archive)
        worksheet_path = _first_worksheet_path(archive)
        with archive.open(worksheet_path) as worksheet:
            for _, row in ET.iterparse(worksheet, events=("end",)):
                if row.tag != f"{{{MAIN_NS}}}row":
                    continue
                values = {"A": "", "B": ""}
                for cell in row.findall(f"{{{MAIN_NS}}}c"):
                    reference = cell.get("r") or ""
                    column = re.match(r"[A-Z]+", reference)
                    if column and column.group(0) in values:
                        values[column.group(0)] = _cell_text(cell, strings).strip()
                yield values["A"], values["B"]
                row.clear()


def _group_districts(catalogs: dict) -> dict[str, list[dict[str, str]]]:
    districts = catalogs["CAT-008"]["entradas"]
    department_codes = [entry["codigo"] for entry in catalogs["CAT-012"]["entradas"]]
    groups: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] = []

    for entry in districts:
        starts_group = entry["codigo"] == "01" or entry["codigo"] == "00"
        if starts_group and current:
            groups.append(current)
            current = []
        current.append(entry)
    if current:
        groups.append(current)

    if len(groups) != len(department_codes):
        raise ValueError(
            f"CAT-008 produjo {len(groups)} grupos, pero CAT-012 contiene {len(department_codes)} departamentos"
        )
    return {code: group for code, group in zip(department_codes, groups, strict=True)}


def build_catalogs(source: Path) -> dict:
    catalogs: dict[str, dict] = {}
    current_id = None

    for code, value in _rows_from_xlsx(source):
        title_match = CATALOG_RE.match(code)
        if title_match:
            current_id, title = title_match.groups()
            if current_id in catalogs:
                raise ValueError(f"Catálogo duplicado: {current_id}")
            catalogs[current_id] = {"titulo": title.strip(), "entradas": []}
            continue

        if not current_id or not code or not value or code.casefold() in HEADER_NAMES:
            continue
        catalogs[current_id]["entradas"].append({"codigo": code, "valor": value})

    if list(catalogs) != EXPECTED_IDS:
        raise ValueError(f"Se esperaban {EXPECTED_IDS}; se encontraron {list(catalogs)}")

    for catalog_id, catalog in catalogs.items():
        if not catalog["entradas"]:
            raise ValueError(f"{catalog_id} quedó sin entradas")
        seen = set()
        for entry in catalog["entradas"]:
            if not entry["codigo"] or not entry["valor"]:
                raise ValueError(f"{catalog_id} contiene una entrada vacía")
            if catalog_id not in REPEATED_CODE_CATALOGS and entry["codigo"] in seen:
                raise ValueError(f"{catalog_id} contiene código duplicado: {entry['codigo']}")
            seen.add(entry["codigo"])

    catalogs["CAT-008"]["entradas_por_departamento"] = _group_districts(catalogs)
    catalogs["CAT-008"]["nota"] = (
        "Los codigos de distrito se repiten entre departamentos; estan agrupados por codigo "
        "de Departamento (CAT-012) en entradas_por_departamento."
    )
    return catalogs


def serialized(catalogs: dict) -> bytes:
    return (json.dumps(catalogs, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Excel oficial de catálogos")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "src" / "config" / "catalogos.json",
        help="JSON de salida",
    )
    parser.add_argument("--check", action="store_true", help="Verifica que el JSON existente sea idéntico")
    args = parser.parse_args()

    if not args.source.is_file():
        parser.error(f"No existe el Excel: {args.source}")

    catalogs = build_catalogs(args.source)
    generated = serialized(catalogs)
    source_sha = hashlib.sha256(args.source.read_bytes()).hexdigest().upper()
    counts = {catalog_id: len(catalog["entradas"]) for catalog_id, catalog in catalogs.items()}

    if args.check:
        if not args.output.is_file() or args.output.read_bytes() != generated:
            print(f"El JSON no coincide con {args.source}", file=sys.stderr)
            return 1
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(generated)

    print(json.dumps({"sourceSha256": source_sha, "total": sum(counts.values()), "counts": counts}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
