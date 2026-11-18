# Biblical books

A reproducible, resumable extraction of **Biblical Studies candidate records from K10plus**, with a pandas-ready Parquet bibliography. No date or language restrictions are imposed by default. Monographs and edited volumes are included. The configuration is deliberately broad; it does **not** establish that every candidate is academic scholarship or that all Biblical Studies books worldwide have been found.

## Setup

```bash
cd ~/Projects/biblical-books
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

Python 3.11+; dependencies are requests, pandas and pyarrow. `requirements.lock.txt` records the exact versions used for validation (Python 3.14 on macOS); optionally install it with `python -m pip install -r requirements.lock.txt` before installing this project. Run commands from the repository root. All downloaded records, raw responses, checkpoints and Parquet files are gitignored.

## Check access and selection first

```bash
biblical-books probe
```

This makes one sequential request per query and prints the count and an example. HTTP 200 can contain an SRU error: the client checks diagnostics and rejects malformed responses. Do not interpret the sum of counts as the number of distinct books.

## Download the entire configured selection

```bash
biblical-books harvest
biblical-books export
```

Run `harvest` again to resume; committed pages are skipped. Run `export` again to update the Parquet files. Stop with Ctrl-C between requests; the current SQLite transaction is atomic. **Run one harvester at a time per data directory.** The default is 100 records/request with a one-second pause, plus retry/backoff for 429 and transient server errors. At hundreds of thousands of records this can take hours. Follow provider restrictions, and consult the service team if rate limits or result-window limits appear; never silently regard a truncated query as complete.

For a bounded smoke run, in its own directory:

```bash
biblical-books --data-dir data/smoke harvest --max-pages 1 --page-size 10
biblical-books --data-dir data/smoke export
```

`--max-pages` limits **new pages per query per invocation**; repeated runs advance the harvest. It is not a permanent cap. Use `--query ddc_bible` to select an individual configured query. `status` and the export manifest say whether every configured query has been downloaded. Incomplete exports are allowed for inspection and are explicitly marked.

```bash
biblical-books status
```

Changing queries or endpoint requires a fresh `--data-dir`. Keep the old directory for provenance. The API is a live catalogue, not a snapshot: counts may change while paging. Count drift is logged, and raw response checksums and retrieval times are retained. Counts and completed page ranges cannot prove snapshot completeness; compare independent fresh harvests for publication-quality work. Query failure stops the process and preserves previous work.

## Load the DataFrame

```python
import pandas as pd

# Textual monographs: MARC leader type a, bibliographic level m.
# Includes edited volumes, print/electronic editions and non-academic books.
df = pd.read_parquet("data/k10plus/books.parquet", dtype_backend="pyarrow")

# Broad candidate set, including articles, serials and other formats.
all_records = pd.read_parquet("data/k10plus/records.parquet", dtype_backend="pyarrow")

# Optional original research scope, applied after collecting metadata:
recent = df[df.publication_year.between(2000, 2025).fillna(False)]
mask = recent.languages.apply(lambda xs: bool(set(xs) & {"eng", "ger", "fre", "deu", "fra"}))
recent = recent[mask]
```

The export streams SQLite rows into bounded Parquet row groups, so creating the files does not load the entire corpus into RAM. Loading a whole pandas DataFrame will require enough RAM, particularly if `marc_json` is included. For analysis, load only needed columns:

```python
df = pd.read_parquet("data/k10plus/books.parquet",
    columns=["record_id", "full_title", "publication_year", "languages", "subjects"],
    dtype_backend="pyarrow")
```

## Files and columns

- `data/k10plus/raw/<query>/<start>.xml.gz`: original SRU responses, including MARC data.
- `harvest.sqlite`: records, query membership and transactionally saved page checkpoints.
- `selection.json`: exact configuration bound to this harvest.
- `status.json`, `export.json`: completion status, advertised counts, export counts and schema.
- `records.parquet`: one row per K10plus record ID in the search union.
- `books.parquet`: subset marked `is_textual_monograph`.

Scalar columns: `record_id`, `source_url`, `title`, `subtitle`, `full_title`, `responsibility`, `publication_year` (nullable), `date_text`, `date_type`, `publication_statement`, `edition`, `extent`, `abstract`, `leader`, `record_type`, `bibliographic_level`, `is_textual_monograph`, `first_seen`, `last_seen`.

Repeated metadata are genuine list columns: `authors` (main-entry names), `editors` (explicit editor roles only), `contributors`, `languages`, `isbns`, `issns`, `dois`, `publishers`, `publication_places`, `subjects`, `subject_authority_ids`, `ddc`, `lcc`, `other_classifications`, `series`, `urls`, `related_record_ids`, `notes`, `matched_queries`.

`marc_json` preserves the MARC leader, all controlfields, indicators and ordered repeated subfields. Original bytes remain in raw responses. The MARC export is a provider conversion from K10plus PICA; losslessness here refers to the returned MARC, not to all underlying PICA/local holdings data.

`publication_year` uses MARC 008 date1 when numeric, otherwise a single unambiguous year in 260/264 $c. Date1 can be an original/reprint/multipart date; inspect `date_type`, `date_text` and `marc_json` before making temporal claims. Unknown dates stay null. Language codes are preserved, not translated. Titles are convenience strings; original punctuation and subfield structure remain in MARC.

## Selection and limits

`config/queries.json` combines DDC 22*, LCC BS*, German and LC subjects, and English/German/French title supplements. Every query is run separately so its contribution is auditable. Primary texts, devotional works and false positives are intentionally retained at this stage. `books.parquet` is a **format filter**, not a validated academic-only corpus.

To improve recall, add verified subject/authority searches for individual biblical books, related ancient literature and relevant academic series. Neighbouring Jewish studies, archaeology, ancient languages, reception and early Christian history are not fully captured by these seeds. Validate against a documented bibliography across languages, dates and publishers; record missing known books before expanding the search. Broad keyword additions can introduce substantial noise. No arbitrary size cap is imposed.

Deduplication is by catalogue ID only. Print/e-book versions, translations and revised editions remain separate; use ISBNs and related IDs to develop a later work-level grouping. Multipart set-level records can be excluded by the strict book filter; they remain in the candidate table when retrieved. The code does not automatically follow related-record links or infer a scholarly/non-scholarly distinction.

## Service documentation

- [K10plus SRU endpoint, query indexes, formats and pagination examples](https://wiki.k10plus.de/spaces/K10PLUS/pages/27361342/SRU)
- [Live Explain/search-index definitions](https://sru.k10plus.de/opac-de-627?version=1.1&operation=explain)
- [K10plus data provision and service conditions](https://wiki.k10plus.de/spaces/K10PLUS/pages/27361297/Datenbereitstellung)

Access, redistribution and metadata licensing should be checked against current provider terms before publishing the dataset. This repository stores code and instructions; metadata remain local and outside Git.
