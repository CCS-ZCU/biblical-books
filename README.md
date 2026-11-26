# biblical-studies-books-mining

A reproducible, resumable extraction of **Biblical Studies candidate records from K10plus**, with a pandas-ready Parquet bibliography. No date or language restrictions are imposed by default. Monographs and edited volumes are included. The configuration is deliberately broad; it does **not** establish that every candidate is academic scholarship or that all Biblical Studies books worldwide have been found.

**The harvest is complete**: all nine configured searches finished on 2026-11-18, giving **525,205 distinct candidate records**, of which **300,542 are textual monographs**. See [`EXTRACTION.md`](EXTRACTION.md) for what that does and does not mean.

## Setup

```bash
cd ~/Projects/biblical-books
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
```

Python 3.11+; dependencies are requests, pandas and pyarrow. `requirements.lock.txt` records the exact versions used for validation (Python 3.14 on macOS); optionally install it with `python -m pip install -r requirements.lock.txt` before installing this project. Run commands from the repository root. All downloaded records, raw responses, checkpoints and Parquet files are gitignored.

## Documentation

| document | contents |
|---|---|
| [`EXTRACTION.md`](EXTRACTION.md) | plain-language account of the source catalogue, the nine searches, what each contributes, and the limits of the result |
| [`DERIVATION.md`](DERIVATION.md) | the offline `derive` step: structured contributors, parsed life dates, GND identifiers, the German–English subject concept map |
| [`NOTEBOOKS.md`](NOTEBOOKS.md) | the three analysis notebooks, their filtering decisions, dependencies and known pitfalls |
| [`VALIDATION.md`](VALIDATION.md) | live checks: pipeline mechanics and the completed full harvest |
| [`AGENTS.md`](AGENTS.md) | operating handoff: setup, harvest/recovery procedure, conventions |

## Licence and citation

Two different things are licensed here, and they are not the same:

| what | licence |
|---|---|
| code and documentation (`src/`, `scripts/`, `tests/`, `*.md`) | **CC BY-SA 4.0** — see [`LICENSE.md`](LICENSE.md) |
| K10plus metadata and every derived table (`books.parquet`, `books_full.parquet`, `contributors.parquet`, `subject_concepts.parquet`) | **CC0**, as published by BSZ, VZG and the participating libraries |

Because the metadata are CC0, a derived bibliography may be redistributed freely; the code that produced it carries the attribution and share-alike terms. Cite the repository via [`CITATION.cff`](CITATION.cff), and state the retrieval date (2026-11-18) and the fact that the result is a candidate set from a live, incomplete catalogue rather than an exhaustive bibliography.

```
Kaše, Vojtěch. biblical-books: reproducible extraction of a Biblical Studies
bibliography from K10plus. https://github.com/kasev/biblical-studies-books-mining
```

## Check access and selection first

```bash
biblical-books probe
```

This makes one sequential request per query and prints the count and an example. HTTP 200 can contain an SRU error: the client checks diagnostics and rejects malformed responses. Do not interpret the sum of counts as the number of distinct books.

## Download the entire configured selection

```bash
biblical-books harvest
biblical-books export
biblical-books derive
```

`derive` is offline and optional: it re-reads the stored MARC and writes `books_full.parquet` plus a
`contributors.parquet` long table with structured names, relator roles, parsed life dates and GND
identifiers. See [`DERIVATION.md`](DERIVATION.md). It can be re-run at any time; `export` output is
left untouched.

Run `harvest` again to resume; committed pages are skipped. Run `export` again to update the Parquet files. Stop with Ctrl-C between requests; the current SQLite transaction is atomic. **Run one harvester at a time per data directory.** The default is 100 records/request with a one-second pause, plus retry/backoff for 429 and transient server errors. At hundreds of thousands of records this can take hours. Follow provider restrictions, and consult the service team if rate limits or result-window limits appear; never silently regard a truncated query as complete.

A record that K10plus cannot serialize is reported as a diagnostic inside its own position while the rest of the page is returned normally. Such positions are skipped **with evidence**: they are listed in the `failures` table and in `status.json` (`skipped_positions`, `unretrievable_records`), and the page is flagged `skipped` in `pages`. The harvest continues instead of blocking every later page; more than one bad record per page (or 5%) is still treated as a systemic failure and stops the run. Query-level diagnostics and malformed responses remain fatal.

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
- `harvest.sqlite`: records, query membership and transactionally saved page checkpoints; the `failures` table lists unretrievable result positions with their page checksum.
- `selection.json`: exact configuration bound to this harvest.
- `status.json`, `export.json`: completion status, advertised counts, export counts and schema.
- `records.parquet`: one row per K10plus record ID in the search union.
- `books.parquet`: subset marked `is_textual_monograph`.
- `books_full.parquet`: `books.parquet` plus derived columns — `contributor_records`, `contributor_types`, `subjects_structured`, `name_authority_ids`, `authority_ids` and a corrected `subject_authority_ids`; `marc_json` omitted (add `derive --keep-marc-json` to retain it).
- `contributors.parquet`: one row per (record, name field) with relator code, name parts, dates and GND ID.
- `subject_concepts.parquet`: the subject concept map — `gnd_id`, a bilingual label such as `Bibel / Bible`, and the observed heading variants.
- `derive.json`: manifest of the derivation, including date-parsing statistics and the concept-map summary.

Scalar columns: `record_id`, `source_url`, `title`, `subtitle`, `full_title`, `responsibility`, `publication_year` (nullable), `date_text`, `date_type`, `publication_statement`, `edition`, `extent`, `abstract`, `leader`, `record_type`, `bibliographic_level`, `is_textual_monograph`, `first_seen`, `last_seen`.

Repeated metadata are genuine list columns: `authors` (main-entry names), `editors` (explicit editor roles only), `contributors`, `languages`, `isbns`, `issns`, `dois`, `publishers`, `publication_places`, `subjects`, `subject_authority_ids`, `ddc`, `lcc`, `other_classifications`, `series`, `urls`, `related_record_ids`, `notes`, `matched_queries`.

In `books_full.parquet`, `authors`/`editors`/`contributors` keep their meaning (flat name strings, now generated from the structured derivation and therefore without the `$d` dates), while `contributor_records` carries the structured form: relator code, inverted-name parts, added terms, GND ID and parsed date range per contributor. `contributors` (flat names) and `contributor_records` (structs) are different columns by design. Because `contributors` is already a superset of `authors` and `editors`, never sum the three.

`marc_json` preserves the MARC leader, all controlfields, indicators and ordered repeated subfields. Original bytes remain in raw responses. The MARC export is a provider conversion from K10plus PICA; losslessness here refers to the returned MARC, not to all underlying PICA/local holdings data.

`publication_year` uses MARC 008 date1 when numeric, otherwise a single unambiguous year in 260/264 $c. Date1 can be an original/reprint/multipart date; inspect `date_type`, `date_text` and `marc_json` before making temporal claims. Unknown dates stay null. Language codes are preserved, not translated. Titles are convenience strings; original punctuation and subfield structure remain in MARC.

## Selection and limits

For a plain-language account of the source catalogue, the nine searches, what each contributes and the known limitations of the completed harvest, read [`EXTRACTION.md`](EXTRACTION.md). The summary below is the technical outline.

`config/queries.json` combines DDC 22*, LCC BS*, German and LC subjects, and English/German/French title supplements. Every query is run separately so its contribution is auditable. Primary texts, devotional works and false positives are intentionally retained at this stage. `books.parquet` is a **format filter**, not a validated academic-only corpus.

To improve recall, add verified subject/authority searches for individual biblical books, related ancient literature and relevant academic series. Neighbouring Jewish studies, archaeology, ancient languages, reception and early Christian history are not fully captured by these seeds. Validate against a documented bibliography across languages, dates and publishers; record missing known books before expanding the search. Broad keyword additions can introduce substantial noise. No arbitrary size cap is imposed.

Deduplication is by catalogue ID only. Print/e-book versions, translations and revised editions remain separate; use ISBNs and related IDs to develop a later work-level grouping. Multipart set-level records can be excluded by the strict book filter; they remain in the candidate table when retrieved. The code does not automatically follow related-record links or infer a scholarly/non-scholarly distinction.

## Service documentation

- [K10plus SRU endpoint, query indexes, formats and pagination examples](https://wiki.k10plus.de/spaces/K10PLUS/pages/27361342/SRU)
- [Live Explain/search-index definitions](https://sru.k10plus.de/opac-de-627?version=1.1&operation=explain)
- [K10plus data provision and service conditions](https://wiki.k10plus.de/spaces/K10PLUS/pages/27361297/Datenbereitstellung)
- [K10plus open data: scope, licence (CC0) and bulk deliveries](https://wiki.k10plus.de/spaces/K10PLUS/pages/358711298/Open+Data)

K10plus catalogue data are published under CC0, so a derived bibliography may be redistributed. Access, metadata licensing and the provider's service conditions should still be checked against the current terms before publishing the dataset. This repository stores code and instructions; metadata remain local and outside Git.

## Repository housekeeping

IDE artifacts (`.idea/`, `*.iml`) and Jupyter checkpoints (`.ipynb_checkpoints/`)
are not tracked. Bulk data and model directories (`large_files/`, `large_data/`)
are never committed; keep large inputs and outputs there. See the
[organizer](https://github.com/kasev/organizer) workspace for the shared workflow.
