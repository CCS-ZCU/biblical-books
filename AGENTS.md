# Agent handoff: K10plus Biblical Studies bibliography

## Objective and scope

Build a large, reproducible bibliography of Biblical Studies monographs and edited volumes from K10plus. The final deliverable is a pandas-ready, gitignored Parquet dataset with individual metadata columns. Hundreds of thousands of records are acceptable: do not narrow to Paul, the Gospels, a particular language, or recent years to reduce volume.

Collect broadly first. The original research question concerned changing title vocabulary in English, German and French during 2000–2025; those restrictions belong in later analysis, not in the default harvest.

The configured searches identify **candidates**, not a proven exhaustive or academic-only corpus. State that distinction in reports. K10plus coverage and incomplete cataloguing prevent a defensible claim that every Biblical Studies book worldwide has been retrieved.

## Current state at handoff (18 November 2026)

- Private repository: https://github.com/kasev/biblical-books
- Original local checkout: `~/Projects/biblical-books`; use an appropriate directory on the server.
- Implementation: `src/biblical_books/cli.py` (SRU, checkpoints, export), `src/biblical_books/marc.py` (metadata parsing), `config/queries.json` (selection).
- Four offline tests passed. See `VALIDATION.md` for the live checks.
- All nine configured queries were tested. Largest query, `pica.sw=Bibel`, advertised 359,124 records; a request near its end returned records successfully. Counts will change and overlap substantially.
- A bounded local smoke harvest produced 68 distinct candidates and 51 textual monographs, each with 39 exported columns. These gitignored files are not on GitHub and will not arrive in a server clone.
- **The full harvest has not run.** The next substantial task is the full server harvest, export and quality assessment.

## Selection strategy

Use the endpoint and separate queries in `config/queries.json`:

1. DDC `22*` and LCC `BS*` classifications.
2. GND subject searches for Bibel, Altes Testament and Neues Testament.
3. Library of Congress subject heading search for Bible.
4. English, French and German title supplements (biblical, biblique*, biblisch*).

Take their union, deduplicated by K10plus record ID. Preserve query membership so each search's contribution can be assessed. Do not sum advertised counts to estimate unique books. Do not impose date, language, or arbitrary size caps during extraction.

After the initial harvest, validate recall against a documented list of known books across languages, periods, publishers and subject areas. Identify gaps before expanding the selection with verified individual-biblical-book subjects, authority IDs, academic series or neighbouring disciplines. The present seeds are not a completed recall-validation exercise.

Changing the configuration, including query descriptions, requires a fresh data directory because the current implementation binds the entire configuration to a harvest. Keep the old directory for comparison. Automatic traversal of related records and work-level deduplication are not implemented.

## Server setup

Use Python 3.11+ with a virtual environment, Git and HTTPS access to GitHub and `sru.k10plus.de`. A private clone requires GitHub authentication on the server; authentication on the original Mac does not automatically transfer. Use the server's existing credentials, or sign in with GitHub CLI (`gh auth login --hostname github.com --git-protocol https --web`) if installed. Never put access tokens in repository URLs or committed files.

```bash
git clone https://github.com/kasev/biblical-books.git
cd biblical-books
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
mkdir -p work
.venv/bin/python -m pip freeze --exclude-editable > work/server-requirements.txt
.venv/bin/biblical-books probe > work/probe.jsonl
```

`requirements.lock.txt` records the versions tested on Python 3.14/macOS. On a different server platform/Python version, install from `pyproject.toml` as above and record the resolved versions; do not assume that file is a universal cross-platform lock.

Inspect all probe results and failures before the full run. Optionally repeat a bounded smoke test in a separate directory:

```bash
.venv/bin/biblical-books --data-dir data/smoke harvest --max-pages 1 --page-size 10
.venv/bin/biblical-books --data-dir data/smoke export
```

`--max-pages` limits NEW pages per query in that invocation. Repeating a smoke command advances it. Production commands below use a separate default directory, `data/k10plus`.

## Full extraction and recovery

Run in a persistent server session such as `tmux` (if installed), so an SSH disconnection does not kill the harvest:

```bash
tmux new -s biblical-books
```

Inside that session, from the repository root:

```bash
.venv/bin/biblical-books harvest > work/harvest.log 2>&1
```

Detach with Ctrl-B, then D; return with `tmux attach -t biblical-books`. Follow progress from another session with `tail -n 40 work/harvest.log`. Expect hours rather than minutes; measure throughput before estimating completion or storage. Raw responses, SQLite, Parquet and temporary export files all consume disk space, so monitor free space.

Run one harvester per data directory. Keep the default sequential requests, 100 records per page and one-second delay. Retries/backoff handle HTTP 429 and transient server errors. Respect provider restrictions; do not increase request concurrency to force throughput. SRU diagnostics, malformed responses and unexpected empty pages are errors, not successful completion.

One exception is deliberate and audited. A single catalogue record can be permanently unretrievable: K10plus then returns HTTP 200 for the whole page with a diagnostic `info:srw/diagnostic/1/63` **inside that position's `recordData`**, while the other 99 records are fine. Refusing the page would block every later page of the query, so the harvester records such positions in the `failures` table (query, position, diagnostic, page SHA-256, raw path), marks the page `skipped=1` in `pages`, logs a warning, and continues. `status.json` reports `skipped_positions`, the full `unretrievable_records` list and a per-query `skipped_positions`; the export manifest carries the same count. Nothing is dropped silently, and a page where more than one record (or 5% of a 100-record page) is unretrievable still raises, because that indicates a systemic fault. Query-level diagnostics, missing result counts and empty pages before the advertised end remain fatal.

On interruption or error, inspect the log, address the cause and run the same harvest command again. Already committed pages are skipped. To preserve earlier logs, use a new log filename or append redirection (`>>`) for a resumed run. Never delete checkpoints just to make a run appear complete.

After `harvest` succeeds:

```bash
.venv/bin/biblical-books status
.venv/bin/biblical-books export
```

Check `selection_complete` is true and every configured query reports complete. Export can also run on a stopped partial harvest for inspection; it does not imply completion. Avoid exporting while a harvester is writing: export does not establish a single read snapshot across all its queries.

The catalogue is live. Offset pagination can skip or repeat records when results change, even if advertised counts stay constant. The implementation warns about count changes, but completed page ranges are not proof of a stable snapshot. For stronger reproducibility, compare a fresh independent harvest and report differences; consider a provider-supplied bulk snapshot if available. If a result-window limit is encountered, investigate supported partitioning or bulk access rather than silently truncating the corpus.

## Outputs and metadata

All harvest outputs are under the selected data directory and excluded from Git:

- `raw/<query>/<start>.xml.gz`: original SRU responses.
- `harvest.sqlite`: record payloads, query membership and page checkpoints.
- `selection.json`: exact configuration.
- `status.json`, `export.json`: completion status, counts and export schema.
- `records.parquet`: all distinct candidate records.
- `books.parquet`: textual-monograph subset (MARC leader type `a`, bibliographic level `m`), including edited volumes.

Metadata include title/subtitle, authors, explicitly identified editors, contributors, publication year/date statement, publishers, publication places, ISBNs, edition, extent, series, languages, subjects, classifications, URLs, related IDs and provenance. Repeated metadata are list columns. Missing values stay missing. Full returned MARC metadata are preserved in `marc_json`; the original response bytes remain in `raw/`.

`books.parquet` is a format filter: it still includes primary texts, devotional books and other non-academic works. Multipart parent records may fall outside the strict filter but remain in the candidate table when retrieved. Print/e-book editions, translations and revised editions remain separate records. Do not collapse them merely because titles match.

Publication year is inferred from numeric MARC 008 date1, otherwise a single unambiguous year in publication statements. Retain `date_type` and `date_text` for interpretation. Date1 can describe reprints or multipart works; forthcoming years can occur legitimately.

## Validation and analysis handoff

Load the completed table:

```python
import pandas as pd

df = pd.read_parquet("data/k10plus/books.parquet", dtype_backend="pyarrow")
assert df.record_id.is_unique
```

Export streams bounded batches into Parquet. Loading all metadata, especially `marc_json`, requires additional RAM; select columns for lightweight checks and analysis.

Report unique candidate and book counts, query completion, date/language distributions, missingness in key metadata, format distribution, and coverage against known books. Inspect samples of classification-only, subject-only and title-only matches for relevance. Keep decisions to exclude records auditable rather than modifying raw evidence. Verify row counts against `export.json` and confirm both Parquet files can be read.

Back up or transfer data separately from Git after stopping writers, including SQLite and any WAL sidecars if present, raw responses, configuration and manifests. Keep exact raw evidence if regenerating parsed metadata later. Do not assume rerunning `export` reparses raw XML: it exports the parsed payloads already in SQLite.

When reporting completion, distinguish successful retrieval of the configured union from validation of an academic Biblical Studies corpus. Provide the server's actual output paths and retrieval dates. Commit code, selection changes and concise validation reports; never commit the datasets, virtual environment, credentials or raw harvest logs.

## Working conventions

Read `README.md` and the relevant source before changing the pipeline. Inspect file sizes before reading unknown files, keep tool output bounded, and process large data locally in chunks. Avoid loading the corpus into chat context. Run the offline tests after substantive code changes; documentation-only updates need command/argument verification, not a new harvest.

Official service references and field details are linked in `README.md`.

## Repository housekeeping

IDE artifacts (`.idea/`, `*.iml`) and Jupyter checkpoints (`.ipynb_checkpoints/`)
are not tracked. Bulk data and model directories (`large_files/`, `large_data/`)
are never committed; keep large inputs and outputs there. See the
[organizer](https://github.com/kasev/organizer) workspace for the shared workflow.
