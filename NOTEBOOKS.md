# Notebooks

The analysis is split into three notebooks that run in order. Each writes its result to disk, so a
later notebook can be re-run without repeating the earlier work.

| # | notebook | input | output |
|---|---|---|---|
| 1 | `scripts/1_explore-k10plus.ipynb` | `data/k10plus/books_full.parquet` | — (prints; one optional plot) |
| 2 | `scripts/2_extracting-21st-century.ipynb` | `books_full.parquet` | `data/k10plus/books_21st_enggerfre.parquet` |
| 3 | `scripts/3_exploring-21st-enggerfre.ipynb` | `books_21st_enggerfre.parquet` | `figures/wordclouds_by_language_decade.png` |

Every notebook locates the data directory the same way, so it runs from `scripts/` or from the
repository root:

```python
DATA_DIR = next(
    (folder / "data/k10plus"
     for folder in [Path.cwd(), *Path.cwd().parents]
     if (folder / "data" / "k10plus" / "export.json").exists()),
    None,
)
```

`data/` is gitignored: the notebooks are committed, the data is not.

## 1. Exploration

Loads `books_full.parquet` (300,542 monographs, 43 columns, no `marc_json`) and works through the
parts of the corpus that a reader must understand before trusting any later number: the export
manifest and completion state, per-query contribution, year and language distributions,
missingness, publishers/subjects/series, sample titles by match type, the 2000–2025 scope, and the
provenance chain back to the archived raw responses.

`books_full.parquet` is written by `biblical-books derive`; see `DERIVATION.md` for what its extra
columns mean.

## 2. Extracting the analysis subset

Produces the file every later step uses. Three filters and one derived column:

```python
books_21st = books[books["publication_year"] >= 2000]                       # open-ended!
books_21st_enggerfre = books_21st[books_21st["languages"].apply(lambda ls: ls[0] in ["eng", "ger", "fre"])]
books_21st_enggerfre["title_cleaned"] = books_21st_enggerfre.apply(
    lambda row: clean_title(row["full_title"], row["languages"]), axis=1)
```

**Result: 78,341 records, 44 columns.**

### Decisions worth knowing

**The year filter is open-ended.** `>= 2000` with no upper bound, so the subset includes 1,249
records dated 2026 and **42 dated 2027** (forthcoming titles the catalogue already describes). If a
closed window is wanted, use `publication_year.between(2000, 2025)`; the counts differ by those 42
records.

**Language is decided by the *first* catalogued code**, not by "any code matches". For this corpus
that gives `eng` 45,876 · `ger` 29,227 · `fre` 3,238. The stricter rule matters because 4,460 records
(5.7%) list more than one language: a bilingual edition, or a translation whose source language is
also recorded. Keeping only the first code assigns each book to a single language, which is what a
per-language comparison needs, but it discards the second language of those records. The looser
alternative — keep a record if *any* of its codes is in the set — gives 79,370 records for the same
period, i.e. about 1,000 more.

**`und` disappears implicitly.** 22,904 monographs (7.6%) carry `und` ("undetermined") as their only
language code, and 186 carry it next to a real code. None can pass the first-language filter, so the
subset is silently free of them. That is defensible for a language-comparison study, but it should be
stated rather than discovered: 7.6% of the corpus has no language claim at all.

**Titles are lemmatised, not just tokenised.** `clean_title` runs the matching spaCy pipeline
(`en_core_web_md`, `de_core_news_md`, `fr_core_news_md`), keeps only `NOUN`, `PROPN`, `ADJ` and
`VERB`, lowercases, and trims punctuation and stray tokens of length 0:

```
Homélies sur le Lévitique Tome 1 (Homélies I - VII)  →  homélie lévitique tome homélie i vii
Jesus Sirach: = Ben Sira                            →  jesus sirach
Psalmen 51 - 100                                    →  psalme
```

Three consequences to keep in mind when reading the word clouds:

- **Numbers are gone.** `51 - 100` is dropped with the other numerals, so volume and part
  information disappears — fine for vocabulary, misleading if you want to count a series.
- **Repeated lemmas are kept.** `homélie` appears twice because nothing deduplicates within a title.
- **Languages outside the three are passed through unchanged**, because `clean_title` returns the
  raw title when no pipeline is loaded. With the filter above this only affects the second language
  of multilingual records.

## 3. Word clouds by language and decade

Builds nine panels (3 languages × 3 decades: 2000–2009, 2010–2019, 2020–2026) from
`title_cleaned`, and saves `figures/wordclouds_by_language_decade.png` at 300 dpi.

Stopwords are per language from NLTK (`english`, `german`, `french`), plus a shared noise list —
`bibel`, `bible`, `testament`, `band`, `bd`, `vol`, `edition` — because these dominate every panel and
say nothing about a period. `collocations=False` is intentional: titles are short already, so bigram
bubbles would crowd out the vocabulary. `random_state=42` keeps the layout reproducible.

## Running them

```bash
# project environment (numpy/pandas/pyarrow only)
.venv/bin/python -m pip install -r requirements.txt

# notebook dependencies: NLTK, spaCy, wordcloud, matplotlib — see requirements-notebooks.txt
.venv/bin/python -m pip install -r requirements-notebooks.txt
.venv/bin/python -m spacy download en_core_web_md
.venv/bin/python -m spacy download de_core_news_md
.venv/bin/python -m spacy download fr_core_news_md
.venv/bin/python -m nltk.downloader stopwords

# verify a notebook without touching its saved outputs
cd scripts && python -m nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 3_exploring-21st-enggerfre.ipynb
```

Verified on 2026-11-24: all three notebooks execute top to bottom; notebook 3 regenerates the figure.

## One trap, and how to avoid it

Notebook 2 writes the subset from a frame that uses `dtype_backend="pyarrow"`. `to_parquet` then
embeds **pandas metadata** describing list columns with an Arrow type string, and a plain read fails:

```
TypeError: data type 'list<element: string>[pyarrow]' not understood
```

The metadata records `"numpy_type": "list<element: string>[pyarrow]"` for all 24 list columns
(`authors`, `editors`, `contributors`, `languages`, `isbns`, …), which pandas hands to `np.dtype()`.

Two ways out, and they are not equivalent:

```python
# preferred: keeps the nested types
sub = pd.read_parquet(path, dtype_backend="pyarrow")
#   languages  list<element: string>[pyarrow]

# what notebook 3 does: drops the metadata, so lists become object arrays of numpy arrays
sub = pq.read_table(path).replace_schema_metadata(None).to_pandas()
#   languages  object  →  array(['fre', 'lat'], dtype=object)
```

The second form is why notebook 3 needs `parse_list`: after stripping the metadata every list cell is
an `ndarray`, and text written with `str()` can carry a literal `\x00`, which `ast.literal_eval`
rejects. If the file is re-read with `dtype_backend="pyarrow"`, `parse_list` is unnecessary and
`languages.list[0]` works directly.

A related indexing detail: `.list[0]` returns a **Series**, so a mask built from it must be combined
on the same frame before filtering. Building the mask from an already-filtered sub-frame and applying
it to the parent raises `IndexingError: Unalignable boolean Series provided as indexer`.

## Files produced

| file | gitignored | meaning |
|---|---|---|
| `data/k10plus/books_21st_enggerfre.parquet` | yes | 78,341 records, 2000+, first language eng/ger/fre, with `title_cleaned` |
| `figures/wordclouds_by_language_decade.png` | no | 3 × 3 word clouds, 300 dpi |

The intermediate Parquet is regenerable from `books_full.parquet` in about a minute, so it is not
committed; the figure is committed because it needs the spaCy models and the intermediate file to
reproduce.
