# 🔄 Rename Record: biblical-books → biblical-studies-books-mining

**Date**: 2026-11-26 21:54 UTC+1  
**Status**: Local rename complete; GitHub rename pending  
**Decision**: Clearer naming (domain + methodology + content explicit)

---

## What Was Changed (Locally)

✅ **CITATION.cff**
- Title: `biblical-books:` → `biblical-studies-books-mining:`
- Repository URL: updated to new GitHub URL

✅ **.zenodo.json**
- Title: updated
- Related identifiers: GitHub URL updated
- JSON structure validated

✅ **pyproject.toml**
- Project name: `biblical-books` → `biblical-studies-books-mining`
- Repository + Homepage URLs: both updated
- Documentation link: updated

✅ **README.md**
- Title: `# Biblical books` → `# biblical-studies-books-mining`
- Repository link: updated

✅ **AGENTS.md**
- Repository link: updated

✅ **ZENODO-READY.md, ZENODO-RELEASE.md**
- All GitHub links: updated
- BibTeX + citation examples: updated

**Git commit**: 5707643 (refactor: Rename to 'biblical-studies-books-mining')

---

## Next Steps (GitHub)

**When ready**:
1. Go to GitHub repo settings: https://github.com/kasev/biblical-books/settings
2. Rename repository to: `biblical-studies-books-mining`
3. GitHub will automatically forward old URL for 1 year
4. Push local changes: `git push`
5. (Optional) Create release tag: `git tag -a v0.1.0 && git push origin v0.1.0`

**See**: `.github/GITHUB-RENAME-STEPS.md` for detailed instructions

---

## Why This Rename?

| Aspect | Before | After |
|--------|--------|-------|
| **Domain clarity** | "biblical-books" (what domain?) | "biblical-studies" (explicit) |
| **Methodology** | Implicit (harvesting?) | "mining" (explicit: NLP/text analysis) |
| **Content** | "books" (all books or specific?) | "biblical-studies-books" (clear scope) |
| **Searchability** | Generic | Keyword-rich (domain + method + content) |

---

## Zenodo Integration Notes

- **Future releases**: Auto-detect new GitHub URL ✅
- **Existing releases**: None yet, so no migration needed
- **DOI generation**: Will use new repository URL going forward
- **Backward compatibility**: Old URL redirects for 1 year on GitHub

---

## Files Involved

- Metadata: CITATION.cff, .zenodo.json, pyproject.toml, README.md, AGENTS.md
- Documentation: ZENODO-READY.md, ZENODO-RELEASE.md
- Instructions: .github/GITHUB-RENAME-STEPS.md (this file)
- Record: RENAME-RECORD.md (this file)

---

**Status**: Ready for GitHub rename. Local state is clean and validated. ✅
