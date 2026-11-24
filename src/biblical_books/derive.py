"""Machine-readable derivation of contributors, dates and authority identifiers.

Input is the ``marc_json`` payload that :func:`biblical_books.export` already stored, so this step
needs **no network access and no re-harvest**: it can be re-run at any time, and its output can be
regenerated from the same evidence.

Why it exists
-------------
The flat export columns lose structure that the catalogue actually provides:

* ``authors``/``editors``/``contributors`` are concatenated name strings, so the relator code
  (``$4 aut|edt|ctb|trl…``), the added terms (``$c``), the GND identifier (``$0``) and the dates
  (``$d``) are unreachable without re-parsing MARC.
* ``editors`` was inferred from ``$4=edt`` *or* an editor word in ``$e``; ``contributors`` was a
  superset of the other two, so the three columns must not be summed.
* ``subject_authority_ids`` was read from subject fields only, so it missed the GND chain in ``689``
  and every authority identifier attached to a *name*.

Outputs (written next to the harvest, all gitignored)
----------------------------------------------------
``books_full.parquet``
    ``books.parquet`` plus derived columns: structured ``contributors``, ``contributor_types``,
    ``subjects_structured``, ``name_authority_ids``, ``authority_ids`` and a corrected
    ``subject_authority_ids``. ``marc_json`` is dropped by default to keep the frame small; pass
    ``--keep-marc-json`` to retain it.
``contributors.parquet``
    One row per (record, name field) — the long table for grouping, joining and faceting.
``derive.json``
    Manifest: input files, counts, and the unresolved-date statistics.

Rules that matter (see ``DERIVATION.md`` for the measurements behind them)
-------------------------------------------------------------------------
* MARC indicator 1 on ``100``/``700`` decides name order: ``1`` is inverted (``Luther, Martin``),
  ``0`` is direct order, ``3`` is a family name. Splitting on the comma without reading the
  indicator mislabels names.
* Corporate bodies (``110``/``710``/``111``/``711``) have no personal-name structure, so
  ``surname``/``forenames`` stay null and ``is_corporate`` is true.
* ``$d`` date strings are heterogeneous (``1483-1546``, ``1961-``, ``260-339``, ``15XX-1627``,
  ``v766-v686``, ``fl. 1803``, ``d. 1755``, ``1697 or 8-1760``, ``10th cent``). Anything that cannot
  be interpreted with confidence is left null in the numeric fields, keeps ``date_text`` verbatim, and
  is counted in ``derive.json`` rather than guessed.
* GND identifiers are extracted as plain IDs plus their resolvable URI
  (``https://d-nb.info/gnd/<id>``). Resolving them to authoritative dates/professions is a separate
  network enrichment and is deliberately not done here.
"""
from __future__ import annotations

import json
import re

import pyarrow as pa

from .marc import LIST_COLUMNS, STRING_COLUMNS

NAME_TAGS = ("100", "110", "111", "700", "710", "711")
PRIMARY_NAME_TAGS = {"100", "110", "111"}
CORPORATE_TAGS = {"110", "111", "710", "711"}
SUBJECT_TAGS = ("600", "610", "611", "630", "648", "650", "651")
CHAIN_TAG = "689"
GND_URI_PREFIX = "https://d-nb.info/gnd/"

# Relator codes occurring in this corpus, most frequent first (see DERIVATION.md).
RELATOR_LABELS = {
    "aut": "author",
    "oth": "other",
    "edt": "editor",
    "ctb": "contributor",
    "prt": "printer",
    "pbl": "publisher",
    "dte": "dedicatee",
    "trl": "translator",
    "ill": "illustrator",
    "hnr": "honoree",
    "adp": "adapter",
    "spn": "sponsor",
}
EDITOR_WORDS = ("editor", "herausgeber", "éditeur", "editeur", "hrsg", "hg.")

_GND = re.compile(r"\(DE-588\)\s*([0-9X][0-9X-]*)")
_SCHEME = re.compile(r"^\(([A-Za-z0-9-]+)\)")
_YEAR = re.compile(r"(?<!\d)(\d{3,4})(?!\d)")
_CENTURY = re.compile(r"(?<!\d)(\d{1,2})\.?\s*(?:st|nd|rd|th)?\s*(?:cent|century|jh)", re.IGNORECASE)
_APPROX = re.compile(r"\b(ca\.?|circa|approximately|approx\.?|about|um)\b", re.IGNORECASE)
_FLORUIT = re.compile(r"\b(fl\.?|floruit|active|tätig)\b", re.IGNORECASE)
# No bare "f"/"d": a single letter would swallow the abbreviation "fl." and misread it as a death date.
_DEATH = re.compile(r"^\s*(d\.|died|gest\.|†)\s*", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"\d*\s*XX")
_VALID_YEAR = range(1, 2100)


def gnd_of(value: str) -> str | None:
    """Return the GND identifier from an authority subfield such as ``(DE-588)118575449``."""
    if not value:
        return None
    match = _GND.search(value)
    return match.group(1) if match else None


def scheme_of(value: str) -> str | None:
    """Return the authority scheme prefix, e.g. ``DE-625`` from ``(DE-625)rvk/123050:``."""
    match = _SCHEME.match(value.strip()) if value else None
    return match.group(1) if match else None


def parse_date_text(text: str | None) -> dict:
    """Parse a MARC ``$d`` date statement into (earliest, latest, precision, flags).

    Conservative by design: returns nulls together with ``date_precision``/``date_flags`` rather
    than a guess, so a caller can filter on how much it trusts a value. ``date_text`` is always kept
    verbatim by the caller.
    """
    result = {
        "date_earliest": None,
        "date_latest": None,
        "date_precision": None,
        "date_flags": [],
    }
    if not text or not text.strip():
        return result

    flags = result["date_flags"]
    work = text.strip().rstrip("?. ").strip()

    if _APPROX.search(work):
        flags.append("approximate")
        work = _APPROX.sub(" ", work).strip()
    if _FLORUIT.search(work):
        flags.append("floruit")
        work = _FLORUIT.sub(" ", work).strip()
    death = _DEATH.match(work)
    if death:
        flags.append("death_only")
        work = work[death.end():].strip()
    work = re.sub(r"^v\.?\s*", "", work)  # "v766" = vixit
    work = work.strip()

    century = _CENTURY.search(work)
    if century:
        flags.append(f"century={int(century.group(1))}")
        # A century statement is not a year range; leave the numeric fields empty.
        if not _YEAR.search(work):
            result["date_precision"] = "century"
            return result

    years = [int(value) for value in _YEAR.findall(work) if int(value) in _VALID_YEAR]
    if not years:
        return result
    if any(int(value) not in _VALID_YEAR for value in _YEAR.findall(work)):
        flags.append("implausible_year")

    if _PLACEHOLDER.search(work):
        # e.g. "15XX-1627": the start is only known to a century, the end is a real year.
        result["date_latest"] = max(years)
        result["date_precision"] = "range_from_unknown"
        return result

    open_end = re.search(r"\d\s*[-–]\s*$", work) is not None
    open_start = re.match(r"^[-–]\s*\d", work) is not None

    if open_end:
        result["date_earliest"] = years[0]
        result["date_precision"] = "open_end"
    elif open_start:
        result["date_latest"] = years[-1]
        result["date_precision"] = "open_start"
    elif len(years) >= 2:
        earliest, latest = min(years[0], years[-1]), max(years[0], years[-1])
        if years[0] > years[-1]:
            flags.append("reversed")
        result["date_earliest"] = earliest
        result["date_latest"] = latest
        result["date_precision"] = "range"
    else:
        year = years[0]
        if "death_only" in flags:
            result["date_latest"] = year
            result["date_precision"] = "death_only"
        else:
            result["date_earliest"] = year
            result["date_latest"] = year
            result["date_precision"] = "floruit" if "floruit" in flags else "year"
    return result


def _values(subfields, codes) -> list[str]:
    return [item["value"].strip() for item in subfields
            if item.get("code") in codes and item.get("value", "").strip()]


def _first(subfields, codes) -> str | None:
    found = _values(subfields, codes)
    return found[0] if found else None


def contributor_row(field: dict, sequence: int) -> dict:
    """Turn one MARC name field into a flat, machine-readable row."""
    tag = field.get("tag", "")
    subfields = field.get("subfields", [])
    codes = {item.get("code") for item in subfields}
    corporate = tag in CORPORATE_TAGS

    relator = _first(subfields, {"4"})
    role_text = " | ".join(_values(subfields, {"e"}))
    # Dates are deliberately excluded: they are in date_text/date_earliest/date_latest, so a name
    # string stays joinable. The legacy flat columns included $d; see DERIVATION.md.
    name = " ".join(_values(subfields, {"a", "b", "c", "q"})).strip()

    inverted = field.get("ind1") == "1"
    surname = forenames = None
    if inverted and not corporate:
        primary = " ".join(_values(subfields, {"a"}))
        if "," in primary:
            head, tail = primary.split(",", 1)
            surname = head.strip()
            forenames = tail.strip() or None

    authority = _values(subfields, {"0"})
    gnd_id = next((gnd_of(value) for value in authority if gnd_of(value)), None)
    others = [value for value in authority if not gnd_of(value)]

    dates = parse_date_text(_first(subfields, {"d"}))

    return {
        "sequence": sequence,
        "marc_tag": tag,
        "is_primary": tag in PRIMARY_NAME_TAGS,
        "is_corporate": corporate,
        "contributor_type": relator,
        "role_text": role_text or None,
        "name_as_catalogued": name or None,
        "name_inverted": inverted,
        "surname": surname,
        "forenames": forenames,
        "name_fuller": " ".join(_values(subfields, {"q"})) or None,
        "name_added_terms": " ".join(_values(subfields, {"c"})) or None,
        "numerals": " ".join(_values(subfields, {"b"})) or None,
        "gnd_id": gnd_id,
        "gnd_uri": GND_URI_PREFIX + gnd_id if gnd_id else None,
        "other_authority_ids": others,
        "affiliation": " ".join(_values(subfields, {"u"})) or None,
        "date_text": _first(subfields, {"d"}),
        "date_earliest": dates["date_earliest"],
        "date_latest": dates["date_latest"],
        "date_precision": dates["date_precision"],
        "date_flags": dates["date_flags"],
        "date_source": "marc_$d" if _first(subfields, {"d"}) else None,
        "related_work_title": " ".join(_values(subfields, {"t"})) or None,
        "has_relator_field": bool(codes & {"4", "e"}),
    }


def subject_row(field: dict, sequence: int) -> dict:
    """Turn one MARC subject field into a flat row with its authority identifiers."""
    subfields = field.get("subfields", [])
    authority = _values(subfields, {"0"})
    gnd_id = next((gnd_of(value) for value in authority if gnd_of(value)), None)
    scheme = _first(subfields, {"2"}) or next((scheme_of(value) for value in authority if scheme_of(value)), None)
    return {
        "sequence": sequence,
        "marc_tag": field.get("tag", ""),
        "scheme": scheme,
        "gnd_id": gnd_id,
        "gnd_uri": GND_URI_PREFIX + gnd_id if gnd_id else None,
        "heading": " ".join(_values(subfields, {"a", "b", "c", "d", "t", "n", "p"})) or None,
        "subdivisions": _values(subfields, {"x", "y", "z", "v"}),
        "authority_ids": authority,
        "full": " ".join(item["value"].strip() for item in subfields
                         if item.get("code") not in {"0", "2", "5", "6", "8"}).strip() or None,
    }


def is_editor(row: dict) -> bool:
    """Editorial role by relator code, falling back to the relator text."""
    if row["contributor_type"] == "edt":
        return True
    text = (row["role_text"] or "").lower()
    return any(word in text for word in EDITOR_WORDS)


def derive(marc_json: str) -> dict:
    """Derive all machine-readable columns for one record."""
    fields = json.loads(marc_json)["fields"]

    contributors, subjects = [], []
    for field in fields:
        tag = field.get("tag", "")
        if "subfields" not in field:
            continue
        if tag in NAME_TAGS:
            contributors.append(contributor_row(field, len(contributors) + 1))
        elif tag in SUBJECT_TAGS or tag == CHAIN_TAG:
            subjects.append(subject_row(field, len(subjects) + 1))

    names = [row["name_as_catalogued"] for row in contributors if row["name_as_catalogued"]]
    primary = [row["name_as_catalogued"] for row in contributors
               if row["is_primary"] and row["name_as_catalogued"]]
    editors = [row["name_as_catalogued"] for row in contributors
               if row["name_as_catalogued"] and is_editor(row)]

    name_authority = [row["gnd_id"] for row in contributors if row["gnd_id"]]
    subject_authority = [row["gnd_id"] for row in subjects if row["gnd_id"]]

    def unique(sequence):
        return list(dict.fromkeys(item for item in sequence if item))

    return {
        "authors": unique(primary),
        "editors": unique(editors),
        "contributors": unique(names),
        "contributor_types": unique(row["contributor_type"] for row in contributors),
        "contributor_records": contributors,
        "subjects_structured": subjects,
        "name_authority_ids": unique(name_authority),
        "subject_authority_ids": unique(subject_authority),
        "authority_ids": unique(name_authority + subject_authority),
    }


# --------------------------------------------------------------------------------------------
# Arrow schemas. Defined explicitly so every batch shares one schema regardless of which optional
# subfield happens to be present in it.
# --------------------------------------------------------------------------------------------
CONTRIBUTOR_STRUCT = pa.struct([
    ("sequence", pa.int32()),
    ("marc_tag", pa.string()),
    ("is_primary", pa.bool_()),
    ("is_corporate", pa.bool_()),
    ("contributor_type", pa.string()),
    ("role_text", pa.string()),
    ("name_as_catalogued", pa.string()),
    ("name_inverted", pa.bool_()),
    ("surname", pa.string()),
    ("forenames", pa.string()),
    ("name_fuller", pa.string()),
    ("name_added_terms", pa.string()),
    ("numerals", pa.string()),
    ("gnd_id", pa.string()),
    ("gnd_uri", pa.string()),
    ("other_authority_ids", pa.list_(pa.string())),
    ("affiliation", pa.string()),
    ("date_text", pa.string()),
    ("date_earliest", pa.int32()),
    ("date_latest", pa.int32()),
    ("date_precision", pa.string()),
    ("date_flags", pa.list_(pa.string())),
    ("date_source", pa.string()),
    ("related_work_title", pa.string()),
])

SUBJECT_STRUCT = pa.struct([
    ("sequence", pa.int32()),
    ("marc_tag", pa.string()),
    ("scheme", pa.string()),
    ("gnd_id", pa.string()),
    ("gnd_uri", pa.string()),
    ("heading", pa.string()),
    ("subdivisions", pa.list_(pa.string())),
    ("authority_ids", pa.list_(pa.string())),
    ("full", pa.string()),
])

DERIVED_COLUMNS = [
    "contributor_types",
    "contributor_records",
    "subjects_structured",
    "name_authority_ids",
    "authority_ids",
]


def books_schema(keep_marc_json: bool = False) -> pa.Schema:
    """Schema of ``books_full.parquet``.

    ``authors``/``editors``/``contributors`` keep their original meaning (flat name strings) so
    existing analysis keeps working; the structured form is ``contributor_records``, and the long
    table ``contributors.parquet`` carries the same facts one row per contributor.
    """
    # `export` writes these three outside STRING_COLUMNS; books_full must stay a superset of
    # books.parquet so that existing analysis keeps working unchanged.
    extra = ["date_type", "first_seen", "last_seen"]
    strings = [name for name in STRING_COLUMNS + extra if keep_marc_json or name != "marc_json"]
    lists = LIST_COLUMNS + ["matched_queries", "name_authority_ids", "authority_ids", "contributor_types"]
    fields = (
        [(name, pa.string()) for name in strings]
        + [(name, pa.list_(pa.string())) for name in lists]
        + [
            ("publication_year", pa.int32()),
            ("is_textual_monograph", pa.bool_()),
            ("contributor_records", pa.list_(CONTRIBUTOR_STRUCT)),
            ("subjects_structured", pa.list_(SUBJECT_STRUCT)),
        ]
    )
    return pa.schema(fields)


CONTRIBUTORS_SCHEMA = pa.schema(
    [("record_id", pa.string())]
    + [(field.name, field.type) for field in CONTRIBUTOR_STRUCT]
    + [("publication_year", pa.int32())]
)
