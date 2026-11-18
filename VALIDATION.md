# Initial validation — 2026-11-18

- All nine configured queries succeeded against the live K10plus SRU service.
- DDC Bible search: 77,510 records; LCC Bible: 56,070; GND Bibel: 359,124. Counts overlap and include multiple publication types.
- Deep pagination: startRecord=359121, maximumRecords=4 on `pica.sw=Bibel` returned four MARC records out of 359,124 advertised matches.
- Bounded extraction: first ten records per query produced 68 unique candidate records and 51 textual monographs in the local, ignored `data/smoke/` directory.
- Both Parquet files were exported and the book table loaded into pandas with 39 columns and unique record IDs.
- Four offline tests passed: repeated MARC fields and editor roles; malformed/diagnostic responses; resume, cross-query union/provenance and Parquet round trip; incomplete harvest reporting.
- Git ignore checks confirmed exclusion of Parquet, downloaded data, checkpoints, raw responses and the virtual environment.

This validates the pipeline mechanics, not recall or precision of the subject selection. The sample is incomplete; a full harvest has not been run. Some live records describe forthcoming publications, so future publication years are preserved.
