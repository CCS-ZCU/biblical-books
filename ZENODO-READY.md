# biblical-books: Zenodo Release Preparation — Complete ✅

**Date:** 2026-11-26  
**Status:** ✅ Repository is fully prepared for Zenodo integration and GitHub release

---

## What Was Done

### 1. **Created `.zenodo.json`** (Zenodo metadata file)
   - Complete metadata structured for Zenodo ingestion
   - Includes title, description, creators with ORCID, keywords, license
   - Validated against Zenodo's strict schema
   - File: [`.zenodo.json`](.zenodo.json)

### 2. **Created `LICENSE.md`** (Full license text)
   - Complete CC BY-SA 4.0 International license text
   - Clarifies dual licensing: code/docs (CC BY-SA 4.0) vs. K10plus metadata (CC0)
   - Addresses Zenodo's requirement for explicit license file
   - File: [`LICENSE.md`](LICENSE.md)

### 3. **Enhanced `CITATION.cff`** (Citation metadata)
   - **Fixed Zenodo compliance issues** (the most common rejection reasons):
     - Date quoted as string to prevent YAML auto-conversion to `datetime.date`
     - ORCID as bare ID (`0000-0002-6601-1605`), not URL
     - Removed duplicate URL fields (`repository`, `url`)
     - Removed problematic `references` section (can cause parsing errors)
     - Kept only single, authoritative `repository-code` field
   - Added version and date-released fields
   - Cleaned abstract for readability
   - File: [`CITATION.cff`](CITATION.cff)

### 4. **Created `ZENODO-RELEASE.md`** (Release guide)
   - Step-by-step instructions for creating GitHub release
   - Guide for Zenodo integration (automatic via GitHub)
   - Detailed release notes template
   - Troubleshooting section for common Zenodo issues
   - File: [`ZENODO-RELEASE.md`](ZENODO-RELEASE.md)

### 5. **Created `scripts/validate-zenodo-metadata.py`** (Pre-release validation)
   - Comprehensive validation script checking:
     - CITATION.cff YAML structure and Zenodo compliance
     - .zenodo.json JSON validity and schema adherence
     - LICENSE.md existence and content
     - Version consistency between pyproject.toml and CITATION.cff
   - Exit code 0 if all checks pass (safe for CI/CD)
   - Provides diagnostic messages for failures
   - File: [`scripts/validate-zenodo-metadata.py`](scripts/validate-zenodo-metadata.py)

### 6. **Validation Results** ✅
```
✓ CITATION.cff: Valid (1 author, 11 keywords)
✓ .zenodo.json: Valid (1 creator, type=software)
✓ LICENSE.md: Exists with CC BY-SA 4.0 text
✓ Version consistency: 0.1.0 (pyproject.toml ↔ CITATION.cff)
```

---

## Critical Metadata Fields (Zenodo Compliance)

### CITATION.cff (CFF 1.2.0 format)
| Field | Value | Status |
|-------|-------|--------|
| `cff-version` | 1.2.0 | ✓ |
| `title` | biblical-books: reproducible K10plus harvesting... | ✓ |
| `authors[0].family-names` | Kaše | ✓ |
| `authors[0].given-names` | Vojtěch | ✓ |
| `authors[0].orcid` | 0000-0002-6601-1605 (ID, not URL) | ✓ |
| `authors[0].affiliation` | Department of Philosophy, Faculty of Arts... | ✓ |
| `license` | CC-BY-SA-4.0 | ✓ |
| `version` | 0.1.0 | ✓ |
| `date-released` | "2026-11-18" (quoted string) | ✓ |
| `repository-code` | https://github.com/kasev/biblical-books | ✓ |
| `keywords` | 11 items (all single words/short phrases) | ✓ |

### .zenodo.json (Zenodo schema)
| Field | Value | Status |
|-------|-------|--------|
| `title` | 83 characters (< 300 max) | ✓ |
| `upload_type` | software | ✓ |
| `license.id` | cc-by-sa-4.0 | ✓ |
| `creators[0].name` | Kaše, Vojtěch | ✓ |
| `creators[0].orcid` | 0000-0002-6601-1605 | ✓ |
| `description` | 692 characters | ✓ |
| `keywords` | 11 items | ✓ |
| `access_right` | open | ✓ |

---

## Why These Changes Matter

### CITATION.cff Pitfalls (Common Zenodo Rejections)
1. **Date format**: YAML automatically converts `2026-11-18` to `datetime.date` object. **Fix**: Quote it as `"2026-11-18"` ✓
2. **ORCID format**: Zenodo expects the bare ID, not the full URL. **Fix**: Use `0000-0002-6601-1605` instead of `https://orcid.org/...` ✓
3. **Duplicate URL fields**: Zenodo parses only one. **Fix**: Keep only `repository-code`, remove `repository` and `url` ✓
4. **References section**: Can cause parsing errors if authors are malformed. **Fix**: Removed (not required; K10plus docs are in .zenodo.json instead) ✓

### .zenodo.json Pitfalls
1. **Title length**: Zenodo has a 300-character limit. **Status**: 83 chars ✓
2. **License ID format**: Must be lowercase with hyphens. **Status**: `cc-by-sa-4.0` ✓
3. **Creator name format**: "Family, Given" is standard. **Status**: "Kaše, Vojtěch" ✓

---

## Next Steps: Create the GitHub Release

### Step 1: Create the Git Tag
```bash
cd /home/jupyter-vojta/notebooks/biblical-books
git tag -a v0.1.0 -m "Initial release: K10plus Biblical Studies harvest (525,205 records, 2026-11-18)"
git push origin v0.1.0
```

### Step 2: Create GitHub Release
1. Go to: https://github.com/kasev/biblical-books/releases/new
2. Select tag: `v0.1.0`
3. Release title: `v0.1.0: K10plus Biblical Studies Bibliography Harvest`
4. Copy release notes from [ZENODO-RELEASE.md](ZENODO-RELEASE.md) → "Example: GreLa Integration" section
5. Click "Publish release"

### Step 3: Zenodo Auto-Archive (24–48 hours)
- Zenodo automatically monitors GitHub releases
- It will ingest the release and generate a DOI
- No manual upload required (unless you prefer)
- Check status: https://zenodo.org/search?q=biblical-books

### Step 4: Update README with DOI Badge (after Zenodo publishes)
Once Zenodo generates the DOI (e.g., `10.5281/zenodo.XXXXXXX`), add to top of README:
```markdown
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)
```

---

## Files Changed

| File | Change | Purpose |
|------|--------|---------|
| `.zenodo.json` | **NEW** | Zenodo metadata (auto-read by Zenodo on release) |
| `LICENSE.md` | **NEW** | Full CC BY-SA 4.0 text (required by Zenodo & pyproject.toml) |
| `CITATION.cff` | **UPDATED** | Fixed compliance issues; added version & date |
| `ZENODO-RELEASE.md` | **NEW** | Release instructions & troubleshooting |
| `scripts/validate-zenodo-metadata.py` | **NEW** | Pre-release validation script |

---

## Validation Command

Before creating any release, run:
```bash
cd /home/jupyter-vojta/notebooks/biblical-books
python3 scripts/validate-zenodo-metadata.py
```

This checks:
- ✓ CITATION.cff format (YAML, fields, ORCID, license, version, date)
- ✓ .zenodo.json validity (JSON, required fields, license ID)
- ✓ LICENSE.md content
- ✓ pyproject.toml ↔ CITATION.cff version consistency

**Exit code 0** = ready to release; **Exit code 1** = issues found

---

## Repository Status

| Component | Status | Notes |
|-----------|--------|-------|
| Code | ✅ Ready | All tests passing, no uncommitted changes |
| Documentation | ✅ Ready | EXTRACTION.md, DERIVATION.md, NOTEBOOKS.md, VALIDATION.md, AGENTS.md |
| Metadata | ✅ Ready | CITATION.cff, .zenodo.json, LICENSE.md all validated |
| Git | ✅ Ready | Changes committed & pushed to main |
| Release-ready | ✅ **YES** | Can create v0.1.0 tag and GitHub release now |

---

## Comparison with GreLa (Reference)

| Aspect | biblical-books | GreLa |
|--------|---|---|
| **CITATION.cff** | ✅ Present & validated | ❌ Not present |
| **.zenodo.json** | ✅ Present & validated | ✅ Present |
| **LICENSE.md** | ✅ Present (CC BY-SA 4.0) | ✅ Present (CC BY-SA 4.0) |
| **DOI badge** | Will add after Zenodo publish | ✅ Has DOI: 10.5281/zenodo.17866142 |
| **Zenodo integration** | ✅ Ready | ✅ Active |
| **GitHub releases** | Ready to create | Multiple (v0.1–v0.7) |

---

## Troubleshooting

### "Zenodo didn't auto-archive after 24 hours"
- Verify `.zenodo.json` is valid JSON (not YAML)
- Ensure it's at repository root (not in subfolder)
- Check GitHub release was created (not just a draft)
- Try manual upload: https://zenodo.org/deposit/

### "CITATION.cff rejected by Zenodo"
- Run `python3 scripts/validate-zenodo-metadata.py` to diagnose
- Most common issues:
  1. Unquoted date (becomes `datetime.date` object) → **Quote it**: `"2026-11-18"`
  2. ORCID as URL → **Use ID only**: `0000-0002-6601-1605`
  3. Multiple URL fields → **Keep one**: `repository-code`
  4. Invalid license → **Use**: `CC-BY-SA-4.0` (hyphens, capitals)

### "Title or keywords rejected"
- Title must be ≤300 characters → **Current**: 83 chars ✓
- Keywords should be single words or short phrases (no special chars)
- Keywords count ≤20 recommended → **Current**: 11 ✓

---

## Citation Examples

After release (copy from CITATION.cff or use Zenodo's auto-generated BibTeX):

**BibTeX:**
```bibtex
@software{kase2026biblicalbooks,
  title = {biblical-books: reproducible K10plus harvesting for a Biblical Studies bibliography},
  author = {Kaše, Vojtěch},
  year = {2026},
  url = {https://github.com/kasev/biblical-books},
  version = {0.1.0}
}
```

**APA:**
```
Kaše, V. (2026). biblical-books: reproducible K10plus harvesting for a Biblical Studies bibliography 
(Version 0.1.0) [Computer software]. https://github.com/kasev/biblical-books
```

**Chicago:**
```
Kaše, Vojtěch. "biblical-books: reproducible K10plus harvesting for a Biblical Studies bibliography." 
GitHub, 2026. https://github.com/kasev/biblical-books.
```

---

## References

- **CFF Format Specification**: https://citation-file-format.github.io/
- **Zenodo Metadata Schema**: https://developers.zenodo.org/#create
- **SPDX License List**: https://spdx.org/licenses/
- **GitHub Guides: Citable Code**: https://guides.github.com/activities/citable-code/
- **Zenodo GitHub Integration**: https://zenodo.org/account/settings/github/

---

## Summary

✅ **biblical-books is now fully prepared for Zenodo integration.**

All metadata files are in place, validated, and committed:
- `.zenodo.json` — Zenodo will read this automatically
- `CITATION.cff` — GitHub/Zenodo citation file, Zenodo-compliant
- `LICENSE.md` — Full license text, required by pyproject.toml
- `scripts/validate-zenodo-metadata.py` — Reusable validation for future releases

**Ready to proceed with creating v0.1.0 release on GitHub.**

Questions or issues? See [ZENODO-RELEASE.md](ZENODO-RELEASE.md) for detailed instructions.
