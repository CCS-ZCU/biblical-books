# Validation

Two records: the initial mechanics check on 2026-11-18, and the completed full harvest.

## Initial validation — 2026-11-18

- All nine configured queries succeeded against the live K10plus SRU service.
- DDC Bible search: 77,510 records; LCC Bible: 56,070; GND Bibel: 359,124. Counts overlap and include multiple publication types.
- Deep pagination: startRecord=359121, maximumRecords=4 on `pica.sw=Bibel` returned four MARC records out of 359,124 advertised matches.
- Bounded extraction: first ten records per query produced 68 unique candidate records and 51 textual monographs in the local, ignored `data/smoke/` directory.
- Both Parquet files were exported and the book table loaded into pandas with 39 columns and unique record IDs.
- Four offline tests passed: repeated MARC fields and editor roles; malformed/diagnostic responses; resume, cross-query union/provenance and Parquet round trip; incomplete harvest reporting.
- Git ignore checks confirmed exclusion of Parquet, downloaded data, checkpoints, raw responses and the virtual environment.

This validated the pipeline mechanics, not recall or precision of the subject selection.

## Full harvest — completed 2026-11-18, exported 2026-11-20

- All nine queries completed: `selection_complete: true` in `status.json` and `export.json`. Retrieval ran
  11:01:50–21:52:02 UTC over 8,564 pages and 856,135 result positions.
- **525,205 distinct candidates; 300,542 textual monographs**, both matching `export.json` exactly and with
  unique `record_id`.
- **One record is permanently unretrievable** (`title_biblisch`, position 17,976): K10plus returns a
  diagnostic `info:srw/diagnostic/1/63` inside that position's `recordData` in every schema
  (`marcxml`, `picaxml`, `dc`, `mods`), reproduced on three separate requests. It is recorded in the
  `failures` table with the page SHA-256 and surfaced as `skipped_positions: 1`; the harvest continued
  past it instead of blocking the remaining 38,668 records of the query.
- **The catalogue drifted while being paged.** `subject_bibel` advertised 359,124 at probe, 359,125
  mid-run and 359,129 at completion; 359,127 distinct records were stored from 359,129 positions. This is
  expected offset-pagination behaviour on a live catalogue, and is why completed page ranges are not
  treated as proof of a snapshot.
- Six offline tests pass, including two added for per-record diagnostics: the audit trail is written
  (failures row, `pages.skipped`, `status.json` counts) and a mostly-unretrievable page still raises.
- Archived raw responses: 654 MB gzip across 8,564 files, one per page, verified by decompressing a
  sample and re-computing its SHA-256 against the `pages` table.
- Data-quality figures reported by `scripts/explore_k10plus.ipynb` were re-checked programmatically
  against the exported files before being written into `EXTRACTION.md`; one figure was corrected in the
  process (the pre-1900 share is 32.1% overall, 30.2% with licensed archive packages excluded).
- Known artefact: 6 records have `publication_year = 0`, because MARC 008 date1 `0000` means "no date"
  but parses as integer zero. Fixing it requires a code change in `marc.py` and a re-export, not a
  re-harvest.

This still validates mechanics and completeness of the *configured* union. It does **not** validate recall
or precision of the subject selection: no comparison against a documented list of known books has been
performed, and `books.parquet` remains a format filter rather than a curated academic corpus.
