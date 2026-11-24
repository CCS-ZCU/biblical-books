# What this extraction is

A plain-language account of the K10plus Biblical Studies harvest: what the source catalogue is,
what we asked it, what came back, and what the result can and cannot support. Technical detail lives
in `README.md`; operating instructions in `AGENTS.md`; run-specific checks in `VALIDATION.md`.

## In one paragraph

We asked K10plus — the shared catalogue of Germany's largest library networks, holding about
78 million book descriptions — for everything a librarian would file under Biblical Studies.
Because books are described in several ways, we searched nine routes at once: two classification
systems (the "shelf"), four subject-heading indexes in German and English, and the words
*biblical*, *biblisch* and *biblique* in titles. The nine searches returned **525,205 different
records**, of which **300,542 are books**; the rest are articles, journals and other formats. No
restriction was placed on date or language, so the set runs from early printed books to forthcoming
titles, in English, German, French, Hebrew, Greek, Latin and several further languages. Every record
keeps its complete original catalogue entry and every raw server response is archived, so any figure
can be traced back and the extraction can be repeated. The catalogue records what its member
libraries *own and describe*, not everything ever published: this is a broad, documented sample, not
a complete list.

## The source catalogue

K10plus is the union catalogue of two large German library networks, created on **25 March 2019** by
merging the databases of the **BSZ** (Bibliotheksservice-Zentrum Baden-Württemberg, which ran the SWB
network) and the **VZG** (Verbundzentrale des GBV, Göttingen). It is the largest bibliographic
database in Germany: roughly **78 million title records** with about **200 million holdings**, covering
university libraries in most German federal states together with Leibniz, Helmholtz and Max Planck
institutes.

A union catalogue does two jobs at once:

1. **Describe a book once.** A library that acquires an already-catalogued title attaches a *holding*
   to the existing description instead of writing a new one. This is why there are far more holdings
   than titles: the descriptions are shared, the ownership is not.
2. **Record who owns what**, so interlibrary loan, acquisition coordination and discovery work across
   the network.

So each record is a *title description* plus a list of *holding libraries*. Local shelf marks and
circulation data are not part of the export; only library identifiers are (MARC field `924`).

K10plus's native format is **PICA+**, and its search indexes carry PICA names — `pica.tit` (title),
`pica.sw` (subject heading), `pica.ddc`, `pica.lcc`. We request `recordSchema=marcxml`, so the
provider converts PICA to MARC 21 on the fly. That conversion is where the non-standard fields in our
records come from (`924` holdings, `689` GND subject chains, `936`/`951` network codes, `583`
preservation actions). "Lossless" here therefore means lossless with respect to the MARC we receive,
not with respect to K10plus.

What it is **not**: not a full-text database (it describes books, not their contents), not a national
bibliography (that is the DNB), and not a complete record of publishing.

## What we asked, and why in nine ways

A subject library can classify, subject-index and title the same book differently, and each route
fails in a different way. Rather than one clever query, nine simple ones were run separately and their
union taken, so every record's route into the corpus is recorded in `matched_queries`.

| Search | In plain language | What it queries | Records found |
|---|---|---|---|
| `ddc_bible` | shelved under "The Bible" in Dewey | DDC 220–229 (`pica.ddc=22*`) | 77,511 |
| `lcc_bible` | in Library of Congress class BS | LCC `BS*` (`pica.lcc=BS*`) | 56,071 |
| `subject_bibel` | German subject heading "Bibel" | GND index (`pica.sw=Bibel`) | **359,129** |
| `subject_bible` | LC subject heading "Bible" | LCSH (`pica.lsh=Bible`) | 88,996 |
| `subject_old_testament` | subject "Altes Testament" | `pica.sw="Altes Testament"` | 87,288 |
| `subject_new_testament` | subject "Neues Testament" | `pica.sw="Neues Testament"` | 78,296 |
| `title_biblical` | "biblical" in the title | `pica.tit=biblical` | 45,393 |
| `title_biblique` | "biblique…" in the title | `pica.tit=biblique*` | 6,883 |
| `title_biblisch` | "biblisch…" in the title | `pica.tit=biblisch*` | 56,568 |

Three independent nets, deliberately:

- **Classification** — the librarian's shelf. Precise about institutional judgement, but sparsely
  applied: only about 44% of our monographs carry an LCC number, and DDC is assigned inconsistently
  across the two merged networks.
- **Subject headings** — the librarian's keywords, in two vocabularies (German GND, American LCSH).
  The dominant net: `pica.sw=Bibel` alone reaches 68% of the corpus. Well populated, but these are
  *aboutness* claims and they inherit cataloguing fashions.
- **Title words** — no librarian required, so this reaches under-catalogued and older material, and is
  the noisiest: the title-only sample contains a 1936 sermon guide and a book on computing in biblical
  scholarship alongside genuine scholarship.

### What each search uniquely contributes

Records that would disappear if that one query were removed:

| Query | Unique to it | Share of all candidates |
|---|---|---|
| `subject_bibel` | 168,316 | 32.0% |
| `title_biblisch` | 45,373 | 8.6% |
| `subject_bible` | 35,366 | 6.7% |
| `title_biblical` | 30,092 | 5.7% |
| `ddc_bible` | 13,338 | 2.5% |
| `title_biblique` | 4,909 | 0.9% |
| `lcc_bible` | 3,679 | 0.7% |
| `subject_old_testament` | 187 | 0.04% |
| `subject_new_testament` | 73 | 0.01% |

Two things to read off this table. The two testament-subject searches are nearly free-riding: 187 and
73 unique records out of 87,288 and 78,296 hits, because they are almost wholly contained in
`pica.sw=Bibel`. The title searches are not decorative — the German one is second only to the main
subject query, and dropping all three title searches would have cost roughly 15% of the corpus.

### How much the searches overlap

Of 525,205 distinct candidates, most were reached by exactly one route:

| reached by N of the 9 searches | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| records | **301,333** | 158,266 | 37,968 | 15,781 | 9,992 | 1,777 | 87 | 1 |

The unique-contribution column sums to exactly 301,333 — the arithmetic check that deduplication and
provenance agree.

## What was deliberately not restricted

These are decisions, not omissions:

- **No date limit.** 19th-century holdings and forthcoming-2027 titles are both in. Applying a
  2000–2025 window later leaves 78,154 of 300,542 books; that loss is visible rather than baked in.
- **No language limit.** `eng` 115,484, `ger` 113,289, `und` 23,090, `lat` 22,240, `fre` 12,737,
  `heb` 7,736, `ita` 5,723, `grc` 4,542, and further down Syriac, Coptic, Arabic and others.
- **No academic-quality filter.** Primary texts, catechisms, devotional works, hymnals and false
  positives are all retained. Judging scholarship is an analysis decision to be documented, not a
  query-time assumption.
- **No work-level collapsing.** Print and e-book editions, translations and revised editions remain
  separate rows, because merging them is lossy and irreversible.

## The one filter that is applied

`books.parquet` is a **format** filter and nothing else: MARC leader type `a` (language material) plus
bibliographic level `m` (monograph), which keeps edited volumes. That is why 525,205 candidates become
300,542 books. It removes articles, serials, maps and scores — not unscholarly content.

## What came back

| | |
|---|---|
| endpoint | `https://sru.k10plus.de/opac-de-627`, MARC 21 XML, 100 records per request, 1 s pause |
| retrieval window | 2026-11-18 11:01:50 – 21:52:02 UTC (8,564 pages, 856,135 result positions) |
| exported | 2026-11-20T15:36:28 UTC |
| distinct candidates | **525,205** |
| textual monographs | **300,542** (57.2%) |
| publication year known | 98.2% |
| archived raw responses | 654 MB gzip, one file per page |

All nine queries completed (`selection_complete: true`). Metadata depth varies by cataloguing practice,
with "missing" counted as either absent or an empty string: no ISBN 58.4%, no series 59.4%, no DDC
62.4%, no LCC 73.4%, no abstract 83.9%, no subtitle 43.5%.

## Limits and known issues

- **Coverage is an acquisition footprint, not a bibliography.** 525,205 records is about 0.7% of the
  catalogue's 78 million titles. A book is here because a German library bought and catalogued it, so
  German- and English-language publishing in German collections is over-represented relative to, say,
  francophone or Latin American scholarship.
- **Historical depth is German library depth.** 32.1% of the monographs (94,784) predate 1900 — a
  property of the holding libraries, not of the research question.
- **Licensed digitised archives are part of the corpus.** 8,269 records (2.8%) belong to e-book and
  microfilm packages, identified by series markers for *Early English Books Online*, *Early American
  Imprints*, *Nineteenth Century Collections Online*, *Making of the Modern World*, *Eighteenth Century
  Collections Online* and *Sabin Americana*. 99.7% of them predate 1900. They are visible in the
  `series` column and should be filtered before any title-vocabulary trend is computed. Note that
  excluding them lowers the pre-1900 share from 32.1% to 30.2%, so quote the figure that matches the
  frame you are describing.
- **The catalogue is live and was paged by offset.** Counts drift while paging: `subject_bibel`
  advertised 359,124 at the probe, 359,125 mid-run and 359,129 at the end, and 359,127 distinct
  records were stored from 359,129 positions. Offset pagination can therefore skip or repeat a record
  even when totals look stable. Completed page ranges are not proof of a snapshot; a fresh independent
  harvest into a new directory and a documented diff is the remedy.
- **One record is permanently unretrievable.** Position 17,976 of `title_biblisch` returns a
  diagnostic (`info:srw/diagnostic/1/63`) instead of MARC, in every schema. It is recorded in the
  `failures` table with the page checksum and reported in `status.json` as `skipped_positions: 1`;
  it is not silently dropped.
- **Six records carry `publication_year = 0`.** MARC 008 date1 `"0000"` means "no date" but parses as
  integer zero; `"9999"` would become 9999. Values of 701–900 are legitimate century approximations.
- **No recall validation has been done.** The searches identify *candidates*. Confirming that a
  documented list of known books was actually retrieved — across languages, periods, publishers and
  subject areas — is the outstanding task before this can be called an academic corpus.
- **`pica.tit=biblical` carries no truncation wildcard**, unlike its French and German siblings, so
  it may miss titles containing only "biblically" or "biblical-" compounds.

## Provenance and licence

K10plus catalogue data is published under **CC0** (public-domain dedication) by BSZ, VZG and the
participating libraries, so a derived bibliography may be published. Attribute the source and state
the retrieval date.

Every figure above can be traced through four artefacts, all gitignored but kept on disk:

| Artefact | What it proves |
|---|---|
| `data/k10plus/raw/<query>/<start>.xml.gz` | the exact bytes returned by the server |
| `harvest.sqlite` — `pages` | retrieval time and SHA-256 per page |
| `harvest.sqlite` — `failures` | the one unretrievable position, with page checksum |
| `data/k10plus/export.json` | completion state, counts and schema of the Parquet files |

`records.parquet` holds all candidates, `books.parquet` the monograph subset, and each row keeps its
full MARC record in `marc_json`. Re-running `export` re-emits the payloads stored in SQLite; it does
not re-parse the archived XML.

## Reproducing

```bash
.venv/bin/biblical-books probe        # one request per query, counts and an example record
.venv/bin/biblical-books harvest      # resumable; ~10 h for this selection at 100 records/request
.venv/bin/biblical-books status
.venv/bin/biblical-books export
.venv/bin/biblical-books derive       # offline: structured contributors, dates, authority IDs
```

`scripts/1_explore-k10plus.ipynb` reproduces every number in this document from the exported files, and
loads `books_full.parquet` — the machine-readable frame written by `derive` (see `DERIVATION.md`).
The two following notebooks extract and visualise the analysis subset; see `NOTEBOOKS.md`.
