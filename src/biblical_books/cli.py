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
    """)
    return db


def session():
    s = requests.Session()
    s.headers["User-Agent"] = "biblical-books/0.1 (bibliographic research; sequential SRU requests)"
    retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"], respect_retry_after_header=True)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def request_page(client, endpoint, cql, start, size):
    response = client.get(endpoint, params={"version": "1.1", "operation": "searchRetrieve", "query": cql, "startRecord": start, "maximumRecords": size, "recordSchema": "marcxml", "recordPacking": "xml"}, timeout=(15, 120))
    response.raise_for_status()
    content = response.content
    root = ET.fromstring(content)
    diagnostics = [" ".join(" ".join(d.itertext()).split()) for d in root.iter() if d.tag.split("}")[-1] == "diagnostic"]
    if diagnostics:
        raise RuntimeError("SRU diagnostic: " + "; ".join(diagnostics))
    number = root.findtext(SRU + "numberOfRecords")
    if number is None:
        raise RuntimeError("Response is not an SRU search response (missing numberOfRecords)")
    wrappers = root.findall(SRU + "records/" + SRU + "record")
    records = []
    for wrapper in wrappers:
        record = wrapper.find(".//" + MARC + "record")
        if record is None:
            raise RuntimeError("SRU record does not contain MARC XML; refusing to skip it")
        records.append(parse_record(record))
    if start <= int(number) and not records and size:
        raise RuntimeError("Empty page before advertised end of results")
    return content, int(number), records


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
                raw, total, records = request_page(client, config["endpoint"], cql, start, args.page_size)
                prior = db.execute("SELECT total FROM pages WHERE query_id=? ORDER BY start LIMIT 1", (qid,)).fetchone()
                if prior and prior[0] != total:
                    LOG.warning("%s: result count changed %s -> %s; catalogue is live, rerun into a fresh directory for comparison", qid, prior[0], total)
                stamp = now()
                raw_path = args.data_dir / "raw" / qid / f"{start:09d}.xml.gz"
                raw_path.parent.mkdir(parents=True, exist_ok=True)
                temp = raw_path.with_suffix(".tmp")
                temp.write_bytes(gzip.compress(raw, mtime=0))
                temp.replace(raw_path)
                with db:
                    for row in records:
                        db.execute("INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload,last_seen=excluded.last_seen", (row["record_id"], json.dumps(row, ensure_ascii=False), stamp, stamp))
                        db.execute("INSERT OR IGNORE INTO hits VALUES (?,?)", (row["record_id"], qid))
                    db.execute("INSERT INTO pages VALUES (?,?,?,?,?,?,?)", (qid, start, len(records), total, stamp, hashlib.sha256(raw).hexdigest(), str(raw_path.relative_to(args.data_dir))))
                LOG.info("%s: %s–%s / %s", qid, start, start + len(records) - 1, total)
                pages += 1
                if not records or start + len(records) > total:
                    break
                start += len(records)
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
        output.append({"id": qid, "cql": cql, "pages": len(pages), "downloaded_occurrences": sum(p[1] for p in pages), "advertised_total": pages[-1][2] if pages else None, "complete": bool(pages) and next_start > pages[-1][2]})
    return output


def status(args):
    db_path = args.data_dir / "harvest.sqlite"
    if not db_path.exists():
        raise ValueError("No harvest database found")
    with closing(connect(db_path)) as db:
        report = {"generated_at": now(), "unique_records": db.execute("SELECT count(*) FROM records").fetchone()[0], "queries": summarize(db)}
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
    schema = schema.with_metadata({b"source": b"K10plus SRU", b"selection_complete": str(report.get("selection_complete", False)).encode(), b"exported_at": now().encode()})
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
        else:
            status(args)
    except (ValueError, RuntimeError, requests.RequestException, ET.ParseError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
