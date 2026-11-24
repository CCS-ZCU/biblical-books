# Derivation: machine-readable contributors, dates and authority IDs

`biblical-books derive` turns the flat export into a frame that can be grouped, joined and faceted
without re-parsing MARC. It is **offline and repeatable**: input is the `marc_json` column that
`export` already stored, so there is no network access, no new harvest, and the same evidence
produces the same output.

```bash
.venv/bin/biblical-books export    # already done: 525,205 candidates / 300,542 monographs
.venv/bin/biblical-books derive    # ~65 s, writes the two files below
```

## Why it is needed

The flat columns lose structure the catalogue actually provides:

| flat column | problem |
|---|---|
| `authors` | a concatenated string, main entries only (1XX), **including added dates** (`Strolz, Walter 1927-2022`) and corporate bodies |
| `editors` | inferred from `$4=edt` **or** an editor word in `$e`; a derived field, not a MARC field |
| `contributors` | a **superset** of `authors` and `editors` — never sum the three |
| `subject_authority_ids` | read from subject fields only: missed the GND chain in `689` and every authority ID on a *name* |

Measured on this corpus: a sample of 26,135 records had a GND ID on a name field in **66.0%** of
records, in the `689` chain in 62.4%, but in the exported `subject_authority_ids` column in only
**22.7%**. 97.8% of name fields carry a `$4` relator code, so the contributor role was there to be
read. Nothing was lost — it is all in `marc_json` — but it was not machine-readable.

## Outputs

| file | rows | contents |
|---|---|---|
| `books_full.parquet` | 300,542 | `books.parquet` plus the derived columns; `marc_json` omitted |
| `contributors.parquet` | 492,785 | one row per (record, name field) — the long table |
| `derive.json` | — | manifest: inputs, counts, date-parsing statistics |

`books.parquet` and `records.parquet` are unchanged, so existing analysis and the provenance chain
still work. `books_full` is a strict **superset** of `books` (plus derived columns, minus
`marc_json`); pass `derive --keep-marc-json` if you need both in one frame (adds ~2.7 GB in memory).

Loading cost, measured in the notebook kernel: **0.2 s** for `books_full.parquet` (98 MB) versus
5.6 GB / 0.6 s for the same rows *with* `marc_json`.

### New columns in `books_full`

| column | type | meaning |
|---|---|---|
| `contributor_records` | `list<struct>` | every name field, structured — see below |
| `contributor_types` | `list<string>` | the relator codes present, e.g. `["aut","edt"]` — cheap filtering |
| `subjects_structured` | `list<struct>` | subjects with heading/subdivision split and their authority IDs |
| `name_authority_ids` | `list<string>` | GND IDs taken from name fields (the gap that was missing) |
| `authority_ids` | `list<string>` | union of name and subject GND IDs, deduplicated |
| `subject_authority_ids` | `list<string>` | **corrected**: now includes the `689` GND chain |

### `contributor_records` structure

```
sequence            position among the record's name fields (1-based, MARC order)
marc_tag            100/110/111 (primary) or 700/710/711 (added entry)
is_primary          tag in 100/110/111
is_corporate        tag in 110/111/710/711
contributor_type    relator code from $4  (aut edt ctb trl prt pbl dte hnr …)
role_text           relator term from $e, as catalogued ("MitwirkendeR", "Herausgeber")
name_as_catalogued  $a $b $c $q  — dates deliberately excluded
name_inverted       indicator 1 == "1"
surname, forenames  split from $a at the first comma, only when inverted and personal
name_fuller         $q  (fuller form of name)
name_added_terms    $c  (titles, honourifics)
numerals            $b
gnd_id, gnd_uri     $0 (DE-588)…  and https://d-nb.info/gnd/<id>
other_authority_ids other $0 schemes, kept verbatim
affiliation         $u
date_text           $d verbatim
date_earliest       int or null
date_latest         int or null
date_precision      year | range | open_end | open_start | floruit | death_only | century | range_from_unknown
date_flags          ["approximate", "floruit", "death_only", "reversed", "century=10", "implausible_year"]
date_source         "marc_$d" — reserved so a GND pass can add "gnd_548" without a schema change
related_work_title  $t, when the 700 carries a related work rather than a person
```

`contributors.parquet` is the same fields flattened, keyed by `record_id`, with `publication_year`
carried along for convenience.

## Decisions, and the evidence for them

**Name order comes from indicator 1, not from the comma.** In this corpus `100`/`700` indicator 1 is
`1` (inverted, `Luther, Martin`) in 65,849 and 66,411 sampled fields respectively, `0` (direct order)
in 2,413 and 4,793, `3` (family name) in 13 and 40. Splitting on the comma without reading the
indicator would mis-assign names in roughly 7% of cases.

**Corporate bodies get no surname.** `110`/`710`/`111`/`711` are organisations and meetings; they
have no personal-name structure. `surname`/`forenames` stay null and `is_corporate` is true. In the
output, 86.0% of contributor rows have a surname — the remainder are corporate or direct-order names.

**Dates are parsed conservatively, and unparsed values are visible.** `$d` is heterogeneous. The 30
most common shapes among 94,987 sampled values were `1483-1546` (56,473), `1961-` (32,927), `-405`
(2,074), `260-339` (918), `1994` (751), `d. 1755` (480), `15XX-1627` (182), `v766-v686` (137),
`approximately …` (78), `fl. 1803` (28), `1697 or 8-1760` (22), `10th cent` (19). The parser handles
these, and leaves the rest null with a flag rather than guessing. Result on the full corpus:

| | |
|---|---|
| contributor rows with `$d` | 310,245 |
| parsed into at least one year | **309,641 (99.8%)** |
| left null, `date_text` preserved | 604 |
| precision `range` | 200,501 |
| precision `open_end` (living / unknown death) | 95,146 |
| `open_start` (death only) | 7,505 |
| `death_only` | 2,442 |
| `year` / `floruit` / `range_from_unknown` / `century` | 3,070 / 243 / 734 / 181 |

Two deliberate abstentions: a century statement (`10th cent`) yields null years plus
`date_flags=["century=10"]`, because turning it into 901–1000 would invent precision the catalogue
did not assert; and a reversed statement (`v766-v686`) is stored as an ordered range with a
`reversed` flag so the oddity stays visible.

**Dates are removed from the name string.** `name_as_catalogued` is `$a $b $c $q`, so a name is
joinable; the dates live in `date_text`/`date_earliest`/`date_latest`. The legacy `authors`,
`editors` and `contributors` columns in `books_full` are now generated from this structure, so they
are internally consistent — but their values therefore differ from `books.parquet` where MARC carried
a `$d`. Anyone needing the old strings should read `books.parquet`.

**`contributors` and `contributor_records` are different columns on purpose.** The former is the flat
list of name strings (backwards compatible); the latter is the structured list. They were briefly the
same name, which silently produced a `contributors` column of strings where a struct was expected.

## What was *not* done

**GND was not resolved.** The IDs are extracted and their URIs constructed, but turning
`(DE-588)118575449` into authoritative dates, professions and a preferred name needs a further
network pass. It is feasible and cheap per request — `https://sru.k10plus.de/opac-de-627!rec=2` with
`pica.ppn=<ppn>` returns the authority record including `548 $a 1483-1546 $4 datl` (Lebensdaten) and
`550 $a Theologe $4 beru` (profession) — but the corpus holds **94,539 distinct GND IDs**
(70,514 on names, 27,260 on subjects, 3,235 in both), so a sequential pass is ~26 h. It belongs in a
separate, cached artefact keyed by GND ID, so that the bibliography stays reproducible without
requiring a network run. `date_source` exists precisely so such a pass can add `gnd_548` values
without a schema change.

**VIAF is not available in this data.** `$1` occurs 44 times in a 94,024-record sample and only with
`ZDB-30-PQE`, a database sigel in field `924` — not a name URI. K10plus publishes GND, not VIAF; a
VIAF identifier would have to come from a GND→VIAF concordance outside this catalogue.

**No work-level grouping and no filtering.** `books_full` keeps one row per catalogue record, as
before. Filtering is the analysis's job; this step only makes the fields addressable.

## Reproducing and checking

```bash
.venv/bin/python -m unittest discover -s tests -v   # 17 tests, incl. 11 for this step
.venv/bin/biblical-books derive
cat data/k10plus/derive.json                        # counts and date statistics
```

The tests pin the behaviour that is easy to regress: indicator-driven name order, editor detection
from `$e` when `$4` is absent, GND coverage of names *and* the `689` chain, the date-shape table
above, that unparsed dates are flagged rather than guessed, that `books_full` is a superset of
`books`, and that `contributors` and `contributor_records` never collide.
