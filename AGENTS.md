# Agent handoff: K10plus Biblical Studies bibliography

## Objective and scope

Build a large, reproducible bibliography of Biblical Studies monographs and edited volumes from K10plus. The final deliverable is a pandas-ready, gitignored Parquet dataset with individual metadata columns. Hundreds of thousands of records are acceptable: do not narrow to Paul, the Gospels, a particular language, or recent years to reduce volume.

Collect broadly first. The original research question concerned changing title vocabulary in English, German and French during 2000–2025; those restrictions belong in later analysis, not in the default harvest.

The configured searches identify **candidates**, not a proven exhaustive or academic-only corpus. State that distinction in reports. K10plus coverage and incomplete cataloguing prevent a defensible claim that every Biblical Studies book worldwide has been retrieved.

## Current state (harvest complete, 20 November 2026)

- Public repository: https://github.com/kasev/biblical-studies-books-mining
- Licence: code and documentation under CC BY-SA 4.0 (`LICENSE.md`); the K10plus metadata and every derived table are CC0, as published by BSZ, VZG and the participating libraries. Citation metadata in `CITATION.cff`.
- Implementation: `src/biblical_books/cli.py` (SRU, checkpoints, export, derive), `src/biblical_books/marc.py` (MARC parsing), `src/biblical_books/derive.py` (structured contributors, dates, authority IDs, subject concepts), `config/queries.json` (selection).
- 22 offline tests pass. See `VALIDATION.md` for the live checks.
- **The full harvest has run and been exported.** All nine queries completed (`selection_complete: true`) on 2026-11-18 between 11:01 and 21:52 UTC: 8,564 pages, 856,135 result positions, **525,205 distinct candidates**, of which **300,542 are textual monographs**. Data on the server at `data/k10plus/` (6.9 GB, including 654 MB of archived raw responses); exported 2026-11-20T15:36:28Z.
- One `title_biblisch` position is permanently unretrievable and is recorded in the `failures` table.
- `scripts/1_explore-k10plus.ipynb` documents the result; **`EXTRACTION.md` is the human-readable account** of the source catalogue, the nine searches and their contributions, and the known limitations.
- **Analysis notebooks (see `NOTEBOOKS.md`)**: `1_explore-k10plus.ipynb` (exploration) → `2_extracting-21st-century.ipynb` (writes `data/k10plus/books_21st_enggerfre.parquet`, 78,341 records, with `title_cleaned`) → `3_exploring-21st-enggerfre.ipynb` (word clouds by language × decade, writes `figures/`). All three execute top to bottom; notebook-only dependencies are pinned in `requirements-notebooks.txt` because the harvest pipeline deliberately stays at requests/pandas/pyarrow.
- **`biblical-books derive` has been run** (offline, two passes, ~2 min): `books_full.parquet` (43 columns, structured `contributor_records` and `subjects_structured` with `concept_id`/`concept_label`/`entity_type`, GND IDs on names *and* subjects, parsed life dates), `contributors.parquet` (492,785 rows) and `subject_concepts.parquet` (88,938 concepts, 88 with a learned bilingual label). 99.8% of `$d` strings parsed; 216,271 records have a GND ID on a name. Decisions and measurements in **`DERIVATION.md`**.
- Still outstanding: recall validation against a documented list of known books (see "Validation and analysis handoff"), work-level deduplication, and the optional GND resolution pass (94,539 distinct IDs, ~26 h sequential — keep it as a separate cached artefact so the bibliography stays reproducible offline).

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

Use Python 3.11+ with a virtual environment, Git and HTTPS access to GitHub and `sru.k10plus.de`. Cloning the repository needs no GitHub authentication because it is public; pushing does. Use the server's existing credentials, or sign in with GitHub CLI (`gh auth login --hostname github.com --git-protocol https --web`) if installed. Never put access tokens in repository URLs or committed files.

```bash
git clone https://github.com/kasev/biblical-studies-books-mining.git
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
- `books_full.parquet`, `contributors.parquet`, `derive.json`: written by `derive` — `books.parquet` plus structured contributors/dates/authority IDs, a long contributor table, and its manifest. See `DERIVATION.md`.

Metadata include title/subtitle, authors, explicitly identified editors, contributors, publication year/date statement, publishers, publication places, ISBNs, edition, extent, series, languages, subjects, classifications, URLs, related IDs and provenance. Repeated metadata are list columns. Missing values stay missing. Full returned MARC metadata are preserved in `marc_json`; the original response bytes remain in `raw/`.

`books.parquet` is a format filter: it still includes primary texts, devotional books and other non-academic works. Multipart parent records may fall outside the strict filter but remain in the candidate table when retrieved. Print/e-book editions, translations and revised editions remain separate records. Do not collapse them merely because titles match.

Publication year is inferred from numeric MARC 008 date1, otherwise a single unambiguous year in publication statements. Retain `date_type` and `date_text` for interpretation. Date1 can describe reprints or multipart works; forthcoming years can occur legitimately.

For analysis, load `books_full.parquet`, not `books.parquet`: it is a superset of the flat columns without `marc_json` (98 MB, ~0.2 s) and adds `contributor_records` (relator code, name parts, GND ID, parsed date range), `subjects_structured` (heading, subdivisions, `entity_type`, `concept_id`, `concept_label`, GND ID), `name_authority_ids` and `authority_ids`. Keep `books.parquet` for the raw MARC and for provenance. `contributors.parquet` is the long table for grouping and joins; `subject_concepts.parquet` maps a GND ID to a bilingual label. Two traps: `contributors` (flat name strings) and `contributor_records` (structs) are different columns, and `contributors` already contains `authors` and `editors`, so never sum the three. Group subjects by `concept_id`, never by `heading`: the same concept is catalogued in German (`689`) and English (LCSH).

## Validation and analysis handoff

Load the completed table:

```python
import pandas as pd

df = pd.read_parquet("data/k10plus/books_full.parquet", dtype_backend="pyarrow")
assert df.record_id.is_unique
```

Export streams bounded batches into Parquet. Loading all metadata, especially `marc_json`, requires additional RAM; select columns for lightweight checks and analysis.

Report unique candidate and book counts, query completion, date/language distributions, missingness in key metadata, format distribution, and coverage against known books. Inspect samples of classification-only, subject-only and title-only matches for relevance. Keep decisions to exclude records auditable rather than modifying raw evidence. Verify row counts against `export.json` and confirm both Parquet files can be read.

Three composition facts to state whenever the corpus is described: 32.1% of monographs predate 1900 (94,784 records — a property of the holding libraries); 8,269 records (2.8%) come from licensed historical e-book/microfilm packages (EEBO, Early American Imprints, Nineteenth Century Collections Online, Making of the Modern World, Eighteenth Century Collections, Sabin Americana) and 99.7% of those predate 1900, so filter on `series` before computing title-vocabulary trends; excluding them the pre-1900 share is 30.2%, so quote whichever frame you mean. Also: 6 records carry `publication_year = 0`, because MARC 008 date1 `0000` denotes "no date" but parses as integer zero. Fixing the last one means treating 0 and 9999 as null in `marc.py` and re-exporting — a re-harvest is not needed.

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
