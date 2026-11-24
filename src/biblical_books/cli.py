"""Resumable, rate-limited SRU harvesting and streaming Parquet export."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import gzip
import hashlib
import json
import logging
from pathlib import Path
import sqlite3
import time
from xml.etree import ElementTree as ET

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .marc import MARC, LIST_COLUMNS, STRING_COLUMNS, parse_record

LOG = logging.getLogger(__name__)
SRU = "{http://www.loc.gov/zing/srw/}"
SRU_DIAGNOSTIC = "{http://www.loc.gov/zing/srw/diagnostic/}"
# A page where this share of records is unretrievable suggests a systemic fault, not one bad record.
MAX_UNRETRIEVABLE_SHARE = 0.05


def now():
    return datetime.now(timezone.utc).isoformat()


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS queries (id TEXT PRIMARY KEY, cql TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, payload TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS hits (record_id TEXT, query_id TEXT, PRIMARY KEY(record_id, query_id));
    CREATE TABLE IF NOT EXISTS pages (query_id TEXT, start INTEGER, count INTEGER, total INTEGER, fetched_at TEXT, sha256 TEXT, raw_path TEXT, PRIMARY KEY(query_id,start));
    CREATE TABLE IF NOT EXISTS failures (query_id TEXT, position INTEGER, diagnostic TEXT, fetched_at TEXT, sha256 TEXT, raw_path TEXT, PRIMARY KEY(query_id,position));
    """)
    # Older databases predate per-record failure tracking; a skipped page position is zero by default.
    if "skipped" not in {row[1] for row in db.execute("PRAGMA table_info(pages)")}:
        db.execute("ALTER TABLE pages ADD COLUMN skipped INTEGER NOT NULL DEFAULT 0")
        db.commit()
    return db


def session():
    s = requests.Session()
    s.headers["User-Agent"] = "biblical-books/0.1 (bibliographic research; sequential SRU requests)"
    retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"], respect_retry_after_header=True)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def request_page(client, endpoint, cql, start, size):
    """Fetch one page, returning (raw bytes, total, records, unretrievable positions).

    A single catalogued record can be unretrievable: K10plus then returns HTTP 200 with a
    diagnostic 63 *inside* that position's recordData while the rest of the page is fine.
    Such positions are returned as failures so the caller can record them explicitly; a
    query-level diagnostic, a missing result count or a mostly unretrievable page still raises.
    """
    response = client.get(endpoint, params={"version": "1.1", "operation": "searchRetrieve", "query": cql, "startRecord": start, "maximumRecords": size, "recordSchema": "marcxml", "recordPacking": "xml"}, timeout=(15, 120))
    response.raise_for_status()
    content = response.content
    root = ET.fromstring(content)
    wrappers = root.findall(SRU + "records/" + SRU + "record")
    records, failures = [], []
    per_record = []
    for index, wrapper in enumerate(wrappers):
        position = wrapper.findtext(SRU + "recordPosition")
        position = int(position) if position and position.strip().isdigit() else start + index
        record = wrapper.find(".//" + MARC + "record")
        if record is not None:
            records.append(parse_record(record))
            continue
        diagnostic = wrapper.find(SRU + "recordData/" + SRU_DIAGNOSTIC + "diagnostic")
        if diagnostic is None:
            raise RuntimeError(f"SRU record at position {position} has neither MARC XML nor a diagnostic; refusing to skip it")
        per_record.append(diagnostic)
        failures.append({"position": position, "diagnostic": " ".join(" ".join(diagnostic.itertext()).split())})
    diagnostics = [" ".join(" ".join(d.itertext()).split()) for d in root.iter(SRU_DIAGNOSTIC + "diagnostic") if not any(d is found for found in per_record)]
    number = root.findtext(SRU + "numberOfRecords")
    if diagnostics or number is None:
        raise RuntimeError("SRU diagnostic: " + ("; ".join(diagnostics) or "Response is not an SRU search response (missing numberOfRecords)"))
    total = int(number)
    # One bad record in a page is a catalogue defect; a page full of them is a systemic fault.
    tolerable = max(1, int(len(wrappers) * MAX_UNRETRIEVABLE_SHARE))
    if len(failures) > tolerable:
        raise RuntimeError(f"{len(failures)} of {len(wrappers)} records unretrievable from startRecord={start}; treating as a systemic failure instead of skipping them")
    if start <= total and not records and not failures and size:
        raise RuntimeError("Empty page before advertised end of results")
    return content, total, records, failures


def config_load(path):
    config = json.loads(path.read_text())
    ids = [q["id"] for q in config["queries"]]
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("Query IDs must be unique, and at least one query is required")
    return config


def select_queries(config, selected):
    if selected:
        unknown = set(selected) - {q["id"] for q in config["queries"]}
        if unknown:
            raise ValueError(f"Unknown query IDs: {sorted(unknown)}")
    return [q for q in config["queries"] if not selected or q["id"] in selected]


def harvest(args):
    config = config_load(args.config)
    # Bind output directory to exact endpoint and queries, preventing accidental mixed corpora.
    args.data_dir.mkdir(parents=True, exist_ok=True)
    config_path = args.data_dir / "selection.json"
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError("Selection changed: use a new --data-dir (or restore the original config)")
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    db = connect(args.data_dir / "harvest.sqlite")
    client = session()
    try:
        for query in select_queries(config, args.query):
            qid, cql = query["id"], query["cql"]
            with db:
                db.execute("INSERT OR IGNORE INTO queries VALUES (?, ?)", (qid, cql))
            pages = 0
            start = 1
            while True:
                previous = db.execute("SELECT count,total FROM pages WHERE query_id=? AND start=?", (qid, start)).fetchone()
                if previous:
                    count, total = previous
                    if count == 0 or start + count > total:
                        break
                    start += count
                    continue
                if args.max_pages is not None and pages >= args.max_pages:
                    LOG.info("%s: stopped at --max-pages; rerun without the limit to continue", qid)
                    break
                time.sleep(args.delay)
                raw, total, records, failures = request_page(client, config["endpoint"], cql, start, args.page_size)
                prior = db.execute("SELECT total FROM pages WHERE query_id=? ORDER BY start LIMIT 1", (qid,)).fetchone()
                if prior and prior[0] != total:
                    LOG.warning("%s: result count changed %s -> %s; catalogue is live, rerun into a fresh directory for comparison", qid, prior[0], total)
                stamp = now()
                raw_path = args.data_dir / "raw" / qid / f"{start:09d}.xml.gz"
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                temp = raw_path.with_suffix(".tmp")
                temp.write_bytes(gzip.compress(raw, mtime=0))
                temp.replace(raw_path)
                digest = hashlib.sha256(raw).hexdigest()
                relative = str(raw_path.relative_to(args.data_dir))
                # Positions consumed, not records stored: an unretrievable position still advances the cursor.
                positions = len(records) + len(failures)
                with db:
                    for row in records:
                        db.execute("INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,last_seen=excluded.last_seen", (row["record_id"], json.dumps(row, ensure_ascii=False), stamp, stamp))
                        db.execute("INSERT OR IGNORE INTO hits VALUES (?,?)", (row["record_id"], qid))
                    for failure in failures:
                        db.execute("INSERT OR REPLACE INTO failures VALUES (?,?,?,?,?,?)", (qid, failure["position"], failure["diagnostic"], stamp, digest, relative))
                    db.execute("INSERT INTO pages (query_id,start,count,total,fetched_at,sha256,raw_path,skipped) VALUES (?,?,?,?,?,?,?,?)", (qid, start, positions, total, stamp, digest, relative, len(failures)))
                for failure in failures:
                    LOG.warning("%s: unretrievable record at position %s of %s (%s); recorded in the failures table, harvest continues", qid, failure["position"], total, failure["diagnostic"])
                LOG.info("%s: %s–%s / %s", qid, start, start + positions - 1, total)
                pages += 1
                if not positions or start + positions > total:
                    break
                start += positions
    finally:
        client.close()
        db.close()
    status(args)


def summarize(db):
    output = []
    for qid, cql in db.execute("SELECT id,cql FROM queries ORDER BY id"):
        pages = db.execute("SELECT start,count,total FROM pages WHERE query_id=? ORDER BY start", (qid,)).fetchall()
        next_start = 1
        for start, count, total in pages:
            if start != next_start:
                break
            next_start += count
        skipped = db.execute("SELECT coalesce(sum(skipped),0) FROM pages WHERE query_id=?", (qid,)).fetchone()[0]
        output.append({"id": qid, "cql": cql, "pages": len(pages), "downloaded_occurrences": sum(p[1] for p in pages), "skipped_positions": skipped, "advertised_total": pages[-1][2] if pages else None, "complete": bool(pages) and next_start > pages[-1][2]})
    return output


def status(args):
    db_path = args.data_dir / "harvest.sqlite"
    if not db_path.exists():
        raise ValueError("No harvest database found")
    with closing(connect(db_path)) as db:
        # Unretrievable positions are listed, never hidden: a complete query may still have them.
        failures = [dict(query_id=qid, position=position, diagnostic=diagnostic, raw_path=raw_path) for qid, position, diagnostic, raw_path in db.execute("SELECT query_id,position,diagnostic,raw_path FROM failures ORDER BY query_id,position")]
        report = {"generated_at": now(), "unique_records": db.execute("SELECT count(*) FROM records").fetchone()[0], "skipped_positions": len(failures), "unretrievable_records": failures, "queries": summarize(db)}
    config_path = args.data_dir / "selection.json"
    if config_path.exists():
        done = {q["id"]: q for q in report["queries"]}
        report["selection_complete"] = all(done.get(q["id"], {}).get("complete", False) for q in config_load(config_path)["queries"])
    (args.data_dir / "status.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return report


def export(args):
    import pyarrow as pa
    import pyarrow.parquet as pq

    report = status(args)
    strings = STRING_COLUMNS + ["date_type", "first_seen", "last_seen"]
    schema = pa.schema([(c, pa.string()) for c in strings] + [(c, pa.list_(pa.string())) for c in LIST_COLUMNS + ["matched_queries"]] + [("publication_year", pa.int32()), ("is_textual_monograph", pa.bool_())])
    schema = schema.with_metadata({b"source": b"K10plus SRU", b"selection_complete": str(report.get("selection_complete", False)).encode(), b"skipped_positions": str(report.get("skipped_positions", 0)).encode(), b"exported_at": now().encode()})
    output = args.data_dir / "records.parquet"
    books = args.data_dir / "books.parquet"
    temp = output.with_suffix(".parquet.tmp")
    books_temp = books.with_suffix(".parquet.tmp")
    count = book_count = 0
    db = connect(args.data_dir / "harvest.sqlite")
    try:
        cursor = db.execute("SELECT id,payload,first_seen,last_seen FROM records ORDER BY id")
        with pq.ParquetWriter(temp, schema, compression="zstd") as writer, pq.ParquetWriter(books_temp, schema, compression="zstd") as book_writer:
            while batch := cursor.fetchmany(args.batch_size):
                rows = []
                # One indexed provenance query per bounded batch, not one query per record.
                first, last = batch[0][0], batch[-1][0]
                hits = {}
                for rid, qid in db.execute("SELECT record_id,query_id FROM hits WHERE record_id>=? AND record_id<=? ORDER BY record_id,query_id", (first, last)):
                    hits.setdefault(rid, []).append(qid)
                for rid, payload, first_seen, last_seen in batch:
                    row = json.loads(payload)
                    row.update(first_seen=first_seen, last_seen=last_seen, matched_queries=hits.get(rid, []))
                    rows.append(row)
                writer.write_table(pa.Table.from_pylist(rows, schema=schema))
                book_rows = [r for r in rows if r["is_textual_monograph"]]
                if book_rows:
                    book_writer.write_table(pa.Table.from_pylist(book_rows, schema=schema))
                count += len(rows)
                book_count += len(book_rows)
        temp.replace(output)
        books_temp.replace(books)
    finally:
        db.close()
    manifest = {"exported_at": now(), "records": count, "textual_monographs": book_count, "status": report, "config": config_load(args.data_dir / "selection.json"), "columns": schema.names}
    (args.data_dir / "export.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    LOG.info("Exported %s candidates and %s textual monographs", count, book_count)


def derive(args):
    """Write books_full.parquet, contributors.parquet and subject_concepts.parquet.

    Offline and repeatable: it reads the ``marc_json`` column already exported, so no network access
    and no re-harvest are involved. Row groups are processed one at a time, so memory stays bounded
    even though ``marc_json`` would be several gigabytes if materialised.

    Two passes are needed. The concept map that merges ``Bibel`` and ``Bible`` into one identity is
    learned from the catalogue itself (records carrying both vocabularies), so it has to be complete
    before any record is written. Pass 1 only counts; pass 2 writes.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    from .derive import (CONCEPT_SCHEMA, CONTRIBUTORS_SCHEMA, ConceptMap, books_schema,
                         derive as derive_record)

    source = args.data_dir / "books.parquet"
    if not source.exists():
        raise ValueError(f"{source} not found; run `biblical-books export` first")

    manifest_path = args.data_dir / "export.json"
    export_manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    schema = books_schema(keep_marc_json=args.keep_marc_json)

    books_path = args.data_dir / "books_full.parquet"
    contributors_path = args.data_dir / "contributors.parquet"
    concepts_path = args.data_dir / "subject_concepts.parquet"
    books_temp = books_path.with_suffix(".parquet.tmp")
    contributors_temp = contributors_path.with_suffix(".parquet.tmp")
    concepts_temp = concepts_path.with_suffix(".parquet.tmp")

    parquet_file = pq.ParquetFile(source)
    groups = parquet_file.num_row_groups

    # --- pass 1: learn the subject concept map ---------------------------------------------
    concepts = ConceptMap()
    for group in range(groups):
        for row in parquet_file.read_row_group(group, columns=["record_id", "marc_json"]).to_pylist():
            concepts.observe(row["record_id"], derive_record(row["marc_json"])["subjects_structured"])
    concepts.build()
    LOG.info("learned concept map: %s", concepts.summary())

    stats = {"records": 0, "contributors": 0, "with_gnd_name": 0, "with_gnd_subject": 0,
             "with_concept": 0, "dates_total": 0, "dates_parsed": 0, "dates_unparsed": 0,
             "precision": {}, "unparsed_examples": [], "concepts": concepts.summary()}
    try:
        with pq.ParquetWriter(books_temp, schema, compression="zstd") as writer, \
                pq.ParquetWriter(contributors_temp, CONTRIBUTORS_SCHEMA, compression="zstd") as contributor_writer:
            for group in range(groups):
                rows = parquet_file.read_row_group(group).to_pylist()
                for row in rows:
                    derived = derive_record(row.pop("marc_json"), concepts)
                    row.update({key: derived[key] for key in
                                ("contributor_types", "name_authority_ids", "authority_ids",
                                 "contributor_records", "subjects_structured",
                                 "subject_authority_ids")})
                    # Keep the compat lists consistent with the structured derivation.
                    for name in ("authors", "editors", "contributors"):
                        row[name] = derived[name]

                    stats["records"] += 1
                    stats["contributors"] += len(derived["contributor_records"])
                    stats["with_gnd_name"] += bool(derived["name_authority_ids"])
                    stats["with_gnd_subject"] += bool(derived["subject_authority_ids"])
                    stats["with_concept"] += bool(derived["subjects_structured"])
                    for contributor in derived["contributor_records"]:
                        if not contributor["date_text"]:
                            continue
                        stats["dates_total"] += 1
                        if contributor["date_earliest"] is None and contributor["date_latest"] is None:
                            stats["dates_unparsed"] += 1
                            if len(stats["unparsed_examples"]) < 25:
                                stats["unparsed_examples"].append(contributor["date_text"])
                        else:
                            stats["dates_parsed"] += 1
                        precision = contributor["date_precision"] or "none"
                        stats["precision"][precision] = stats["precision"].get(precision, 0) + 1
                writer.write_table(pa.Table.from_pylist(
                    [{name: row.get(name) for name in schema.names} for row in rows], schema=schema))
                long_rows = []
                for row in rows:
                    for contributor in row["contributor_records"]:
                        long_rows.append({"record_id": row["record_id"], **contributor,
                                          "publication_year": row.get("publication_year")})
                if long_rows:
                    contributor_writer.write_table(pa.Table.from_pylist(long_rows, schema=CONTRIBUTORS_SCHEMA))
                LOG.info("derived row group %s/%s: %s records, %s contributors so far",
                         group + 1, groups, stats["records"], stats["contributors"])
        books_temp.replace(books_path)
        contributors_temp.replace(contributors_path)
        pq.write_table(pa.Table.from_pylist(concepts.table(), schema=CONCEPT_SCHEMA),
                       concepts_temp, compression="zstd")
        concepts_temp.replace(concepts_path)
    finally:
        books_temp.unlink(missing_ok=True)
        contributors_temp.unlink(missing_ok=True)
        concepts_temp.unlink(missing_ok=True)

    manifest = {
        "derived_at": now(),
        "source": {"books": str(source.name), "exported_at": export_manifest.get("exported_at"),
                   "records": export_manifest.get("textual_monographs")},
        "outputs": {"books": books_path.name, "contributors": contributors_path.name,
                    "concepts": concepts_path.name, "books_columns": schema.names},
        "keep_marc_json": bool(args.keep_marc_json),
        "stats": stats,
    }
    (args.data_dir / "derive.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    LOG.info("Derived %s records and %s contributor rows into %s and %s",
             stats["records"], stats["contributors"], books_path.name, contributors_path.name)
    print(json.dumps({key: stats[key] for key in ("records", "contributors", "with_gnd_name",
                                                 "with_gnd_subject", "with_concept", "dates_total",
                                                 "dates_parsed", "dates_unparsed", "concepts")},
                     indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/queries.json"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/k10plus"))
    sub = parser.add_subparsers(dest="command", required=True)
    probe = sub.add_parser("probe", help="Check configured queries, counts and one record each")
    probe.add_argument("--query", action="append")
    get = sub.add_parser("harvest", help="Download or resume raw records")
    get.add_argument("--query", action="append")
    get.add_argument("--page-size", type=int, default=100)
    get.add_argument("--delay", type=float, default=1.0)
    get.add_argument("--max-pages", type=int, help="Maximum NEW pages per query in this invocation")
    sub.add_parser("status")
    out = sub.add_parser("export")
    out.add_argument("--batch-size", type=int, default=5000)
    rich = sub.add_parser("derive", help="Derive structured contributors, dates and authority IDs offline")
    rich.add_argument("--keep-marc-json", action="store_true",
                      help="Retain marc_json in books_full.parquet (adds ~2.7 GB in memory when loaded)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        if args.command == "probe":
            config = config_load(args.config)
            with session() as client:
                for q in select_queries(config, args.query):
                    _, total, rows = request_page(client, config["endpoint"], q["cql"], 1, 1)
                    print(json.dumps({"id": q["id"], "cql": q["cql"], "total": total, "example": {k: rows[0][k] for k in ("record_id", "full_title", "record_type", "bibliographic_level")} if rows else None}, ensure_ascii=False), flush=True)
                    time.sleep(1)
        elif args.command == "harvest":
            if not 1 <= args.page_size <= 100 or args.delay < 0.5 or args.max_pages is not None and args.max_pages < 1:
                raise ValueError("Use page-size 1–100, delay >=0.5 seconds, max-pages >=1")
            harvest(args)
        elif args.command == "export":
            if args.batch_size < 1:
                raise ValueError("batch-size must be positive")
            export(args)
        elif args.command == "derive":
            derive(args)
        else:
            status(args)
    except (ValueError, RuntimeError, requests.RequestException, ET.ParseError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
