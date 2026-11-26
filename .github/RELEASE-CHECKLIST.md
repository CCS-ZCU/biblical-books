# Release Checklist for biblical-books

**Use this checklist before creating each GitHub release.**

## Pre-Release (Day -1)

- [ ] Run validation: `python3 scripts/validate-zenodo-metadata.py`
- [ ] Verify all tests pass: `python -m unittest discover -s tests -v`
- [ ] Check git status: `git status` (should show clean working tree)
- [ ] Review CITATION.cff and .zenodo.json one final time

## Release Day (Day 0)

### 1. Create Git Tag
```bash
git tag -a v0.1.0 -m "Initial release: K10plus Biblical Studies harvest (525,205 records, 2026-11-18)"
git push origin v0.1.0
```

### 2. Create GitHub Release
1. Go to: https://github.com/CCS-ZCU/biblical-books/releases/new
2. Tag: `v0.1.0`
3. Title: `v0.1.0: K10plus Biblical Studies Bibliography Harvest`
4. Description: Paste from [ZENODO-RELEASE.md](../ZENODO-RELEASE.md)
5. ✅ Click "Publish release"

## Post-Release (Day +1 to +2)

- [ ] Check Zenodo: https://zenodo.org/search?q=biblical-books
  - Wait 24–48 hours for auto-archive
  - Verify DOI is assigned
  - Verify metadata are correct
- [ ] Get DOI from Zenodo (format: `10.5281/zenodo.XXXXXXX`)
- [ ] Update README.md with DOI badge at top:
  ```markdown
  [![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)
  ```
- [ ] Commit badge update:
  ```bash
  git add README.md
  git commit -m "Add Zenodo DOI badge"
  git push origin main
  ```

## Verification Checklist

**After release appears on Zenodo:**

- [ ] Title matches CITATION.cff
- [ ] Author name and ORCID are correct
- [ ] License is CC-BY-SA-4.0
- [ ] Keywords are present (11 items)
- [ ] Description is readable
- [ ] Version number matches tag: `v0.1.0`
- [ ] Upload type is "software"
- [ ] Access right is "open"

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Zenodo didn't auto-archive" | Check release was published (not draft); wait 48h; manually upload if needed |
| "Metadata rejected" | Run `validate-zenodo-metadata.py`; check error message |
| "ORCID not recognized" | Use bare ID (`0000-0002-6601-1605`), not URL |
| "Date format error" | Ensure CITATION.cff has quoted date: `"2026-11-18"` |

## For Future Releases (v0.2.0+)

1. Update version in `pyproject.toml` and `CITATION.cff`
2. Update date-released in `CITATION.cff` to new release date
3. Run `python3 scripts/validate-zenodo-metadata.py`
4. Create tag: `git tag -a v0.2.0 -m "Release v0.2.0"`
5. Push: `git push origin v0.2.0`
6. Create GitHub Release (Zenodo will auto-archive)

---

**Documentation:** See [ZENODO-RELEASE.md](../ZENODO-RELEASE.md) and [ZENODO-READY.md](../ZENODO-READY.md) for detailed instructions.
