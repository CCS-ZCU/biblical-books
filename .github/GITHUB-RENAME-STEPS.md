# 🔄 GitHub Repository Rename: Final Steps

**Status**: Local rename ✅ COMPLETE  
**Next Step**: GitHub rename (requires web interface)

---

## Step 1: Go to GitHub Repository Settings

1. Navigate to: https://github.com/kasev/biblical-books/settings
2. Find the "Repository name" field (top of General settings)
3. Change from: `biblical-books`
4. Change to: `biblical-studies-books-mining`
5. Click "Rename"

**Expected**: GitHub shows confirmation message "Repository renamed"

---

## Step 2: Verify GitHub Forwarding

GitHub automatically redirects the old URL (`biblical-books`) to the new one (`biblical-studies-books-mining`) for 1 year.

After rename, verify:
- Old URL works: https://github.com/kasev/biblical-books (should redirect)
- New URL works: https://github.com/kasev/biblical-studies-books-mining
- Both show the same repository content

---

## Step 3: Update Local Clone (Optional)

Your local clone can stay at the old URL (GitHub redirects work), but you can update it to use the new URL:

```bash
cd ~/notebooks/biblical-books

# Check current remote
git remote -v

# Update remote URL to new repository
git remote set-url origin https://github.com/kasev/biblical-studies-books-mining.git

# Verify
git remote -v
```

**Note**: The local commits you just made are already compatible with both URLs.

---

## Step 4: Push Changes

```bash
cd ~/notebooks/biblical-books

# Your commits are ready (you're on main branch)
git push

# After GitHub rename, this will push to the new repository URL
```

**Note**: The first push after GitHub rename may take a moment as GitHub updates the repository state.

---

## ✅ Verification Checklist

After completing all steps:

- [ ] GitHub shows new repository name `biblical-studies-books-mining`
- [ ] Old URL `biblical-books` redirects to new URL
- [ ] New repository URL is accessible
- [ ] Local commits pushed successfully
- [ ] CITATION.cff metadata matches new URL
- [ ] .zenodo.json metadata matches new URL

---

## 🎉 When You're Ready for Zenodo

After GitHub rename is complete, create a first release:

```bash
cd ~/notebooks/biblical-books

# Create a git tag
git tag -a v0.1.0 -m "First release: biblical studies bibliography from K10plus"

# Push tag to GitHub
git push origin v0.1.0

# Then go to GitHub releases page and create release from tag
# Zenodo will auto-detect the new repository URL
```

Zenodo will then:
1. Auto-detect the new repository
2. Generate a DOI for the release
3. Update metadata with new repository URL
4. Make it citable

---

## 📝 Timeline

- ✅ Local rename complete (commit 5707643)
- ⏳ GitHub rename (you do this via web interface)
- ⏳ Push local changes (after GitHub rename)
- ⏳ Create GitHub release (optional, for Zenodo)
- ⏳ Verify Zenodo auto-detection (happens automatically)

---

**Ready to rename on GitHub?** When you go to the GitHub settings, you'll see the rename field exactly as described above.

If you have any questions during the rename, the GitHub interface is very clear and shows "Renaming..." status.
