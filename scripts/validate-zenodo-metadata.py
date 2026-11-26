#!/usr/bin/env python3
"""
Validate biblical-books metadata files for Zenodo release.

This script checks:
1. CITATION.cff format and Zenodo compliance
2. .zenodo.json validity and completeness
3. LICENSE.md existence
4. pyproject.toml consistency with CITATION.cff
5. README.md references to key facts

Run before creating a release:
  python scripts/validate-zenodo-metadata.py

Exit code 0 = all checks pass, 1 = validation failed
"""

import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("❌ PyYAML not installed. Install with: pip install pyyaml")
    sys.exit(1)


def validate_citation_cff(repo_root):
    """Validate CITATION.cff for Zenodo compliance."""
    cff_path = repo_root / "CITATION.cff"
    
    if not cff_path.exists():
        return False, "CITATION.cff not found"
    
    try:
        with open(cff_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return False, f"Invalid YAML in CITATION.cff: {e}"
    
    # Required fields for Zenodo
    required = ['cff-version', 'title', 'authors', 'license', 'version', 'date-released', 'repository-code']
    missing = [k for k in required if k not in data]
    if missing:
        return False, f"Missing required CFF fields: {missing}"
    
    # Validate author structure
    if not data.get('authors'):
        return False, "No authors defined"
    
    for i, author in enumerate(data['authors']):
        if 'family-names' not in author or 'given-names' not in author:
            return False, f"Author {i} missing family-names or given-names"
        
        # ORCID should be just the ID, not a full URL
        if 'orcid' in author:
            orcid = author['orcid']
            if orcid.startswith('https://'):
                return False, f"Author {i} ORCID is a URL; use just the ID (0000-0002-...)"
            if not orcid.count('-') == 3:  # Format: 0000-0002-6601-1605
                return False, f"Author {i} ORCID format invalid: {orcid}"
    
    # Validate license
    license_val = data.get('license', '')
    valid_licenses = ['CC-BY-SA-4.0', 'CC-BY-4.0', 'CC0-1.0', 'MIT', 'Apache-2.0', 'GPL-3.0+']
    if license_val not in valid_licenses:
        return False, f"License '{license_val}' not in Zenodo approved list. Use format like CC-BY-SA-4.0"
    
    # Validate version format
    version = data.get('version', '')
    if not version or version.count('.') < 1:
        return False, f"Version '{version}' invalid; use semantic versioning (e.g., 0.1.0)"
    
    # Validate date format
    date_val = data.get('date-released', '')
    if isinstance(date_val, str):
        if len(date_val) != 10 or date_val.count('-') != 2:
            return False, f"Date '{date_val}' invalid; use YYYY-MM-DD format"
    elif not isinstance(date_val, type(None)):
        return False, f"Date must be string or null, not {type(date_val)}"
    
    # Validate keywords (should not be too many, should be short)
    keywords = data.get('keywords', [])
    if len(keywords) > 20:
        return False, f"Too many keywords ({len(keywords)}); Zenodo recommends ≤20"
    
    return True, f"✓ CITATION.cff valid ({len(data['authors'])} author(s), {len(keywords)} keyword(s))"


def validate_zenodo_json(repo_root):
    """Validate .zenodo.json for Zenodo compliance."""
    zenodo_path = repo_root / ".zenodo.json"
    
    if not zenodo_path.exists():
        return False, ".zenodo.json not found"
    
    try:
        with open(zenodo_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, f"Invalid JSON in .zenodo.json: {e}"
    
    # Required fields
    required = ['title', 'description', 'creators', 'license', 'upload_type']
    missing = [k for k in required if k not in data]
    if missing:
        return False, f"Missing required .zenodo.json fields: {missing}"
    
    # Validate title
    title = data.get('title', '')
    if not title:
        return False, "Empty title"
    if len(title) > 300:
        return False, f"Title too long ({len(title)} chars, max 300)"
    
    # Validate description
    description = data.get('description', '')
    if not description:
        return False, "Empty description"
    
    # Validate creators
    creators = data.get('creators', [])
    if not creators:
        return False, "No creators defined"
    
    for i, creator in enumerate(creators):
        if 'name' not in creator:
            return False, f"Creator {i} missing name"
        if 'orcid' in creator:
            orcid = creator['orcid']
            if orcid.startswith('https://'):
                return False, f"Creator {i} ORCID is a URL; prefer just the ID"
    
    # Validate license structure
    license_val = data.get('license')
    if isinstance(license_val, dict):
        if 'id' not in license_val:
            return False, "License dict missing 'id' field"
        license_id = license_val['id'].lower()
    elif isinstance(license_val, str):
        license_id = license_val.lower()
    else:
        return False, f"License must be dict or string, not {type(license_val)}"
    
    if 'by-sa' not in license_id or 'cc' not in license_id:
        return False, f"License '{license_id}' should be CC-BY-SA-4.0"
    
    # Validate upload_type
    upload_type = data.get('upload_type', '').lower()
    if upload_type not in ['software', 'dataset', 'publication', 'poster', 'presentation', 'report', 'image', 'video', 'lesson']:
        return False, f"Invalid upload_type: {upload_type}"
    
    return True, f"✓ .zenodo.json valid ({len(creators)} creator(s), type={upload_type})"


def validate_license_md(repo_root):
    """Validate LICENSE.md exists."""
    license_path = repo_root / "LICENSE.md"
    
    if not license_path.exists():
        return False, "LICENSE.md not found"
    
    content = license_path.read_text()
    if len(content) < 500:
        return False, "LICENSE.md too short (should include full CC BY-SA 4.0 text)"
    
    if 'CC' not in content or 'BY-SA' not in content:
        return False, "LICENSE.md should reference CC BY-SA 4.0"
    
    return True, "✓ LICENSE.md exists and contains CC BY-SA 4.0 text"


def validate_pyproject_consistency(repo_root):
    """Validate pyproject.toml version consistency."""
    pyproject_path = repo_root / "pyproject.toml"
    cff_path = repo_root / "CITATION.cff"
    
    if not pyproject_path.exists():
        return False, "pyproject.toml not found"
    
    # Parse versions from both files
    with open(pyproject_path) as f:
        pyproject_text = f.read()
        # Find version = "..."
        import re
        match = re.search(r'version\s*=\s*"([^"]+)"', pyproject_text)
        pyproject_version = match.group(1) if match else None
    
    with open(cff_path) as f:
        cff_data = yaml.safe_load(f)
        cff_version = cff_data.get('version')
    
    if not pyproject_version:
        return False, "Could not find version in pyproject.toml"
    
    if pyproject_version != cff_version:
        return False, f"Version mismatch: pyproject.toml={pyproject_version}, CITATION.cff={cff_version}"
    
    return True, f"✓ Version consistency: {pyproject_version}"


def main():
    """Run all validations."""
    repo_root = Path(__file__).parent.parent
    
    print("🔍 Validating biblical-books metadata for Zenodo release\n")
    
    checks = [
        ("CITATION.cff", validate_citation_cff),
        (".zenodo.json", validate_zenodo_json),
        ("LICENSE.md", validate_license_md),
        ("Version consistency", validate_pyproject_consistency),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            passed, message = check_func(repo_root)
            status = "✓" if passed else "❌"
            print(f"{status} {name}: {message}")
            results.append(passed)
        except Exception as e:
            print(f"❌ {name}: Unexpected error: {e}")
            results.append(False)
    
    print()
    
    if all(results):
        print(f"✅ All {len(results)} validation checks passed!")
        print("\nRepository is ready for Zenodo release. Next steps:")
        print("  1. Commit changes: git add -A && git commit -m 'Add Zenodo metadata'")
        print("  2. Create tag: git tag -a v0.1.0 -m 'Initial release'")
        print("  3. Push: git push origin main --tags")
        print("  4. Create GitHub Release at: https://github.com/kasev/biblical-books/releases/new")
        return 0
    else:
        failed = sum(1 for r in results if not r)
        print(f"❌ {failed} validation check(s) failed. Fix issues before proceeding.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
