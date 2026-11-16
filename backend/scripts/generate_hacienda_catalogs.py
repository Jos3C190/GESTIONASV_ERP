"""Genera los catálogos de Hacienda para el DTE a partir del Excel oficial.

Uso (desde ``backend/``)::

    uv run python scripts/generate_hacienda_catalogs.py \
        "ruta/Catálogos - Facturación Electrónica (1 julio).xlsx"

Escribe ``app/infrastructure/catalogs/hacienda_dte.py`` (los 33 catálogos) y
``app/infrastructure/catalogs/hacienda_geography.py`` (códigos de Hacienda de
la geografía que ya usa el ERP). El Excel se lee como ZIP con XML, con
``defusedxml``; se ejecuta en el contenedor del backend, que ya lo tiene.

Al publicar Hacienda una versión nueva del Excel, se actualiza ``VERSION`` y
``VERSION_DATE``, se ejecuta este script y se revisa el diff.
"""

from __future__ import annotations

import re
import sys
import unicodedata
import zipfile
from pathlib import Path

from defusedxml import ElementTree

VERSION = "1.1"
VERSION_DATE = "2026-07"
EXPECTED_CATALOGS = 33

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.infrastructure.catalogs.el_salvador_geography import GEOGRAPHY  # noqa: E402

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

#: CAT-015 se divide en secciones; la sección es parte de la llave porque D4 y
#: D5 aparecen en las dos primeras.
TAX_SECTIONS = {"1": "summary", "2": "body", "3": "informative"}

#: Distritos cuyo nombre abreviado en Hacienda no permite enlazarlos solos.
DISTRICT_OVERRIDES = {("La Unión", "La Unión Norte", "San José La Fuente"): "15"}

ABBREVIATIONS = {
    "STA": "SANTA",
    "STGO": "SANTIAGO",
    "STG": "SANTIAGO",
    "SN": "SAN",
    "NVA": "NUEVA",
    "NVO": "NUEVO",
    "ANTGO": "ANTIGUO",
    "D": "DE",
    "MA": "MARIA",
    "FCO": "FRANCISCO",
    "ANT": "ANTONIO",
    "MIG": "MIGUEL",
    "RAF": "RAFAEL",
    "EST": "ESTEBAN",
    "CAY": "CAYETANO",
    "CONCEP": "CONCEPCION",
    "ORAT": "ORATORIO",
    "PTO": "PUERTO",
    "OTE": "ORIENTE",
    "MEANG": "MEANGUERA",
    "DELIC": "DELICIAS",
    "NOM": "NOMBRE",
    "HERR": "HERRADURA",
}
CONNECTORS = {"DE", "LA", "DEL", "LAS", "LOS"}


def _norm(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value.upper())
    plain = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return " ".join(plain.replace(".", " ").split())


def _col(ref: str) -> int:
    letters = re.match(r"[A-Z]+", ref)
    assert letters is not None
    index = 0
    for ch in letters.group(0):
        index = index * 26 + ord(ch) - 64
    return index - 1


def read_rows(xlsx: Path) -> list[list[str]]:
    with zipfile.ZipFile(xlsx) as book:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ElementTree.fromstring(book.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", NS):
                shared.append("".join(t.text or "" for t in item.iter(f"{{{NS['m']}}}t")))
        workbook = ElementTree.fromstring(book.read("xl/workbook.xml"))
        rels = ElementTree.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target") for rel in rels}
        sheets = workbook.find("m:sheets", NS)
        assert sheets is not None, "El libro no tiene hojas"
        assert len(sheets) == 1, "Se esperaba una sola hoja"
        target = str(targets[sheets[0].get(REL)])
        sheet = ElementTree.fromstring(book.read("xl/" + target.lstrip("/").removeprefix("xl/")))
    rows: list[list[str]] = []
    for row in sheet.iter(f"{{{NS['m']}}}row"):
        values: dict[int, str] = {}
        for cell in row.findall("m:c", NS):
            kind = cell.get("t")
            raw = cell.find("m:v", NS)
            if kind == "inlineStr":
                text = "".join(t.text or "" for t in cell.iter(f"{{{NS['m']}}}t"))
            elif raw is None or raw.text is None:
                continue
            elif kind == "s":
                text = shared[int(raw.text)]
            else:
                text = raw.text
            text = " ".join(text.split())
            if text:
                values[_col(str(cell.get("r")))] = text
        if values:
            rows.append([values[i] for i in sorted(values)])
    return rows


def split_catalogs(rows: list[list[str]]) -> dict[str, dict[str, object]]:
    catalogs: dict[str, dict[str, object]] = {}
    current: dict[str, object] | None = None
    header_pending = False
    for cells in rows:
        match = re.match(r"^(CAT-\d{3})\s+(.*)$", cells[0])
        if match and len(cells) == 1:
            current = {"title": match.group(2).strip(), "rows": []}
            catalogs[match.group(1)] = current
            header_pending = True
            continue
        if current is None:
            continue
        if header_pending:
            header_pending = False
            continue
        rows_list = current["rows"]
        assert isinstance(rows_list, list)
        rows_list.append(cells)
    assert len(catalogs) == EXPECTED_CATALOGS, (
        f"Se esperaban {EXPECTED_CATALOGS} catálogos, hay {len(catalogs)}"
    )
    return catalogs


def build_items(  # noqa: C901 - un caso por particularidad del Excel
    catalogs: dict[str, dict[str, object]],
) -> dict[str, tuple[str, list[tuple[str, str, str]]]]:
    """Devuelve ``{catálogo: (título, [(grupo, código, nombre)])}``."""
    departments = [
        row[0]
        for row in catalogs["CAT-012"]["rows"]
        if row[0] != "00"  # type: ignore[union-attr]
    ]
    out: dict[str, tuple[str, list[tuple[str, str, str]]]] = {}
    for key, data in catalogs.items():
        title = str(data["title"])
        rows = data["rows"]
        assert isinstance(rows, list)
        items: list[tuple[str, str, str]] = []
        group = ""
        district_department = -1
        municipality_department = 0
        previous_municipality_prefix = ""
        for cells in rows:
            if len(cells) == 1:
                heading = cells[0]
                if key == "CAT-015":
                    section = re.match(r"^(\d)-", heading)
                    assert section is not None, heading
                    group = TAX_SECTIONS[section.group(1)]
                # CAT-019: títulos de sector; CAT-014: notas al pie. No son códigos.
                continue
            code, name = cells[0], cells[1]
            if key == "CAT-014":
                name = re.sub(r"\s+\d(?:\s*,\s*\d)*$", "", name)
            if key == "CAT-008" and code != "00":
                if code == "01":
                    district_department += 1
                group = departments[district_department]
            if key == "CAT-013" and code != "00":
                prefix = _norm(name).rsplit(" ", 1)[0]
                if previous_municipality_prefix and prefix != previous_municipality_prefix:
                    municipality_department += 1
                previous_municipality_prefix = prefix
                group = departments[municipality_department]
            if key in ("CAT-008", "CAT-013") and code == "00":
                group = ""
            items.append((group, code, name))
        keys = [(g, c) for g, c, _ in items]
        assert len(keys) == len(set(keys)), f"Códigos repetidos en {key}"
        out[key] = (title, items)
    return out


def match_geography(
    items: dict[str, tuple[str, list[tuple[str, str, str]]]],
) -> tuple[dict[str, str], dict[tuple[str, str], str], dict[tuple[str, str, str], str]]:
    departments = {_norm(name): code for _, code, name in items["CAT-012"][1] if code != "00"}
    department_codes: dict[str, str] = {}
    municipality_codes: dict[tuple[str, str], str] = {}
    district_codes: dict[tuple[str, str, str], str] = {}
    for department, municipalities in GEOGRAPHY.items():
        dep_code = departments[_norm(department)]
        department_codes[department] = dep_code
        dep_munis = [(c, n) for g, c, n in items["CAT-013"][1] if g == dep_code]
        dep_districts = [(c, n) for g, c, n in items["CAT-008"][1] if g == dep_code]
        used: set[str] = set()
        for municipality, districts in municipalities.items():
            hits = [c for c, n in dep_munis if _norm(n) == _norm(municipality)]
            assert len(hits) == 1, (department, municipality)
            municipality_codes[(department, municipality)] = hits[0]
            for district in districts:
                key = (department, municipality, district)
                code = DISTRICT_OVERRIDES.get(key) or _match_district(district, dep_districts)
                assert code not in used, (key, code)
                used.add(code)
                district_codes[key] = code
        assert len(used) == len(dep_districts), (department, len(used), len(dep_districts))
    return department_codes, municipality_codes, district_codes


def _match_district(district: str, candidates: list[tuple[str, str]]) -> str:
    target = _norm(district)
    wanted = [t for t in target.split() if t not in CONNECTORS]
    found: list[str] = []
    for code, name in candidates:
        if _norm(name) == target:
            return code
        tokens = [ABBREVIATIONS.get(t, t) for t in _norm(name).split()]
        tokens = [t for t in tokens if t not in CONNECTORS]
        if len(tokens) == len(wanted) and all(
            w.startswith(t) for t, w in zip(tokens, wanted, strict=True)
        ):
            found.append(code)
    assert len(found) == 1, (district, found)
    return found[0]


def _literal(value: str) -> str:
    return repr(value)


def write_catalogs(items: dict[str, tuple[str, list[tuple[str, str, str]]]], path: Path) -> None:
    lines = [
        '"""Catálogos del sistema de transmisión de DTE del Ministerio de Hacienda.',
        "",
        f"Fuente: «Catálogos - Facturación Electrónica», versión {VERSION} ({VERSION_DATE}).",
        "Generado por ``scripts/generate_hacienda_catalogs.py``; no editar a mano.",
        "",
        "Cada catálogo es ``(título, ((grupo, código, nombre), ...))``. El grupo es el",
        "código de departamento en CAT-008 y CAT-013 (sus códigos se repiten entre",
        "departamentos) y la sección en CAT-015 (D4 y D5 aparecen en dos secciones).",
        '"""',
        "",
        f"CATALOG_VERSION = {_literal(VERSION)}",
        f"CATALOG_VERSION_DATE = {_literal(VERSION_DATE)}",
        "",
        "CATALOGS: dict[str, tuple[str, tuple[tuple[str, str, str], ...]]] = {",
    ]
    for key in sorted(items):
        title, rows = items[key]
        lines.append(f"    {_literal(key)}: (")
        lines.append(f"        {_literal(title)},")
        lines.append("        (")
        for group, code, name in rows:
            lines.append(f"            ({_literal(group)}, {_literal(code)}, {_literal(name)}),")
        lines.append("        ),")
        lines.append("    ),")
    lines.append("}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_geography(
    departments: dict[str, str],
    municipalities: dict[tuple[str, str], str],
    districts: dict[tuple[str, str, str], str],
    path: Path,
) -> None:
    lines = [
        '"""Códigos de Hacienda (CAT-012, CAT-013 y CAT-008) de la geografía del ERP.',
        "",
        f"Catálogos versión {VERSION} ({VERSION_DATE}). Las llaves son los nombres de",
        "``el_salvador_geography.GEOGRAPHY``. Generado por",
        "``scripts/generate_hacienda_catalogs.py``; no editar a mano.",
        '"""',
        "",
        "DEPARTMENT_CODES: dict[str, str] = {",
        *(f"    {_literal(k)}: {_literal(v)}," for k, v in departments.items()),
        "}",
        "",
        "MUNICIPALITY_CODES: dict[tuple[str, str], str] = {",
        *(
            f"    ({_literal(a)}, {_literal(b)}): {_literal(v)},"
            for (a, b), v in municipalities.items()
        ),
        "}",
        "",
        "DISTRICT_CODES: dict[tuple[str, str, str], str] = {",
        *(
            f"    ({_literal(a)}, {_literal(b)}, {_literal(c)}): {_literal(v)},"
            for (a, b, c), v in districts.items()
        ),
        "}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    if len(sys.argv) != len(("script", "xlsx")):
        raise SystemExit(__doc__)
    items = build_items(split_catalogs(read_rows(Path(sys.argv[1]))))
    departments, municipalities, districts = match_geography(items)
    target = BACKEND / "app" / "infrastructure" / "catalogs"
    write_catalogs(items, target / "hacienda_dte.py")
    write_geography(departments, municipalities, districts, target / "hacienda_geography.py")
    total = sum(len(rows) for _, rows in items.values())
    print(f"{len(items)} catálogos, {total} códigos; {len(districts)} distritos enlazados.")


if __name__ == "__main__":
    main()
