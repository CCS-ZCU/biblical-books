"""Lossless MARC capture with convenient, deliberately conservative columns."""
import json
import re
from xml.etree import ElementTree as ET

MARC = "{http://www.loc.gov/MARC21/slim}"
LIST_COLUMNS = ["authors", "editors", "contributors", "languages", "isbns", "issns", "dois", "publishers", "publication_places", "subjects", "subject_authority_ids", "ddc", "lcc", "other_classifications", "series", "urls", "related_record_ids", "notes"]
STRING_COLUMNS = ["record_id", "source_url", "leader", "record_type", "bibliographic_level", "title", "subtitle", "full_title", "responsibility", "publication_statement", "date_text", "edition", "extent", "abstract", "marc_json"]


def parse_record(record: ET.Element) -> dict:
    leader = record.findtext(MARC + "leader", "")
    fields = []
    for child in record:
        tag = child.tag.removeprefix(MARC)
        if tag == "controlfield":
            fields.append({"tag": child.get("tag"), "value": child.text or ""})
        elif tag == "datafield":
            fields.append({"tag": child.get("tag"), "ind1": child.get("ind1", " "), "ind2": child.get("ind2", " "), "subfields": [{"code": s.get("code"), "value": s.text or ""} for s in child]})

    def values(tags, codes=None):
        return [s["value"] for f in fields if f["tag"] in tags for s in f.get("subfields", []) if codes is None or s["code"] in codes]

    def joined(tags, codes=None):
        return [" ".join(s["value"] for s in f.get("subfields", []) if codes is None or s["code"] in codes) for f in fields if f["tag"] in tags]

    def control(tag):
        return next((f["value"] for f in fields if f["tag"] == tag and "value" in f), "")

    record_id = control("001")
    if not record_id:
        raise ValueError("MARC record has no 001 identifier")
    fixed = control("008")
    title = " ".join(values({"245"}, {"a", "n", "p"})).strip(" /:")
    subtitle = " ".join(values({"245"}, {"b"})).strip(" /:")
    publication = joined({"260", "264"}, {"a", "b", "c"})
    dates = values({"260", "264"}, {"c"})
    year_text = fixed[7:11] if len(fixed) >= 11 else ""
    # 008 date1 may describe an original edition/reprint; retain date type and full statement.
    year = int(year_text) if re.fullmatch(r"\d{4}", year_text) else None
    if year is None:
        years = re.findall(r"(?<!\d)(?:1[0-9]{3}|20[0-9]{2})(?!\d)", " ".join(dates))
        year = int(years[0]) if len(set(years)) == 1 else None
    editors = []
    contributors = []
    for field in fields:
        if field["tag"] in {"100", "110", "111", "700", "710", "711"}:
            subs = field.get("subfields", [])
            name = " ".join(s["value"] for s in subs if s["code"] in {"a", "b", "c", "d", "q"})
            contributors.append(name)
            if any(s["code"] == "4" and s["value"] == "edt" or s["code"] == "e" and any(t in s["value"].lower() for t in ("editor", "herausgeber", "éditeur")) for s in subs):
                editors.append(name)
    languages = values({"041"}, {"a"})
    if len(fixed) >= 38 and fixed[35:38].strip():
        languages.append(fixed[35:38])
    result = dict(record_id=record_id, source_url=f"https://opac.k10plus.de/DB=2.299/PPNSET?PPN={record_id}", leader=leader, record_type=leader[6:7], bibliographic_level=leader[7:8], title=title, subtitle=subtitle, full_title=title + (": " + subtitle if subtitle else ""), responsibility=" ".join(values({"245"}, {"c"})), publication_statement=" | ".join(publication), date_text=" | ".join(dates), publication_year=year, date_type=fixed[6:7], edition=" | ".join(joined({"250"})), extent=" | ".join(joined({"300"})), abstract=" | ".join(joined({"520"})), authors=joined({"100", "110", "111"}, {"a", "b", "c", "d", "q"}), editors=editors, contributors=contributors, languages=languages, isbns=values({"020"}, {"a"}), issns=values({"022"}, {"a"}), dois=[s["value"] for f in fields if f["tag"] == "024" and any(s["code"] == "2" and s["value"].lower() == "doi" for s in f.get("subfields", [])) for s in f.get("subfields", []) if s["code"] == "a"], publishers=values({"260", "264"}, {"b"}), publication_places=values({"260", "264"}, {"a"}), subjects=joined({"600", "610", "611", "630", "648", "650", "651", "653", "655"}, {"a", "b", "c", "d", "t", "v", "x", "y", "z"}), subject_authority_ids=values({"600", "610", "611", "630", "648", "650", "651"}, {"0", "1"}), ddc=values({"082", "083"}, {"a"}), lcc=values({"050"}, {"a", "b"}), other_classifications=joined({"084"}), series=joined({"490", "830"}, {"a", "n", "p", "v"}), urls=values({"856"}, {"u"}), related_record_ids=values({"773", "774", "775", "776", "780", "785", "787"}, {"w"}), notes=joined({"500", "502", "504", "505", "533", "534", "546"}), marc_json=json.dumps({"leader": leader, "fields": fields}, ensure_ascii=False), is_textual_monograph=leader[6:7] == "a" and leader[7:8] == "m")
    for col in LIST_COLUMNS:
        result[col] = list(dict.fromkeys(x for x in result[col] if x))
    return result
