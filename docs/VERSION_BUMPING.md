# Version Bumping Guide

## Overview

The `bump_version.py` script automates the process of bumping version numbers across your project using semantic versioning.

## Semantic Versioning

The project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0) - Incompatible API changes
- **MINOR** (0.X.0) - New backward-compatible functionality
- **PATCH** (0.0.X) - Bug fixes and patches

Format: `MAJOR.MINOR.PATCH`

Examples:
- `1.0.0` → `2.0.0` (major bump)
- `1.0.0` → `1.1.0` (minor bump)
- `1.0.0` → `1.0.1` (patch bump)

## Usage

### Basic Usage

```bash
# Bump major version
python bump_version.py major

# Bump minor version
python bump_version.py minor

# Bump patch version
python bump_version.py patch
```

### Example Output

```
======================================================================
🔄 Cyber-Lighthouse Version Bumper
======================================================================

Current version: 1.0.0

📊 Version Bump: PATCH
   1.0.0 → 1.0.1

📝 Files to update:
   ✓ pyproject.toml
   ✓ setup.py

Proceed with version bump? (yes/no): yes

🔧 Updating files...

✅ Updated pyproject.toml: 1.0.0 → 1.0.1
✅ Updated setup.py: 1.0.0 → 1.0.1

Commit these changes to git? (yes/no): yes

✅ Committed version bump: 1.0.1

Create git tag for this release? (yes/no): yes

✅ Created git tag: v1.0.1

======================================================================
✅ Version Bump Complete!
======================================================================

New version: 1.0.1
Tag: v1.0.1

Next steps:
  1. Verify changes: git log -1
  2. Push changes: git push origin master
  3. Push tag: git push origin v1.0.1
```

## Files Updated

The script automatically updates version numbers in:

| File | Purpose |
|------|---------|
| `pyproject.toml` | Python project metadata |
| `setup.py` | Python package setup |

## Features

### Interactive Confirmation

The script asks for confirmation at each step:

1. **Version bump**: Confirm the new version
2. **Git commit**: Ask if you want to commit changes
3. **Git tag**: Ask if you want to create a release tag

This prevents accidental version bumps.

### Git Integration

- Automatically commits version changes
- Creates annotated git tags
- Provides push instructions

### Safe Updates

- Checks if files exist before updating
- Only updates first occurrence (prevents accidental overwrites)
- Reports success/failure for each file
- Handles errors gracefully

## When to Bump Versions

### Major Version (X.0.0)

Bump when:
- Removing or renaming core features
- Changing database schema in incompatible ways
- Major architectural changes
- Breaking API changes

Example: Semantic clustering feature added (would be minor in initial release)

### Minor Version (0.X.0)

Bump when:
- Adding new features (backward compatible)
- Adding new command-line options
- Expanding documentation
- Performance improvements

Examples:
- Added web scraping with trafilatura
- Added daily summary generation
- Added Teams webhook integration

### Patch Version (0.0.X)

Bump when:
- Bug fixes
- Security patches
- Documentation corrections
- Minor performance tweaks

Examples:
- Fixed database locking issue
- Fixed cache clearing
- Updated logging messages

## Release Workflow

### 1. Prepare Release

```bash
# Ensure all changes are committed
git status

# Run tests
python -m pytest tests/

# Update CHANGELOG.md (optional)
```

### 2. Bump Version

```bash
# Choose appropriate bump type
python bump_version.py minor
```

### 3. Verify Changes

```bash
# Check the commit
git log -1

# Check the tag
git tag -l -n1
```

### 4. Push to Remote

```bash
# Push commits
git push origin master

# Push tags
git push origin v1.1.0
```

### 5. Create Release

On GitHub:
1. Go to Releases
2. Click "Draft a new release"
3. Select tag `v1.1.0`
4. Add release notes
5. Publish release

## Advanced Usage

### Manual Version Bump

If you want to update versions manually:

```bash
# Edit files directly
nano pyproject.toml
nano setup.py

# Commit
git add pyproject.toml setup.py
git commit -m "Bump version to 1.1.0"

# Create tag
git tag -a v1.1.0 -m "Release version 1.1.0"
```

### Skip Git Operations

If you only want to update files without git operations:

1. Edit `bump_version.py`
2. Remove or comment out git-related code
3. Run the script

Or manually update files and skip git steps during interactive prompts.

### Custom Version Format

To update other files with version numbers:

1. Edit `FILES_TO_UPDATE` in `bump_version.py`
2. Add new file paths
3. Run the script

Example:

```python
FILES_TO_UPDATE = [
    "pyproject.toml",
    "setup.py",
    "README.md",  # Add this
    "docs/conf.py",  # Add this
]
```

## Troubleshooting

### Version Not Found

**Problem**: "No version found in file"

**Solution**:
- Check file format matches `X.Y.Z` pattern
- Ensure version is on a line by itself or with standard format
- Manually update the file

### Git Commit Failed

**Problem**: "Error committing version bump"

**Causes**:
- Uncommitted changes preventing commit
- Git not installed
- Git configuration incomplete

**Solution**:
```bash
# Commit manually
git add -A
git commit -m "Bump version to X.Y.Z"
```

### Git Tag Already Exists

**Problem**: "Git tag v1.0.0 already exists"

**Solution**:
- Delete the tag: `git tag -d v1.0.0`
- Or use a different version
- Or force-create: `git tag -a -f v1.0.0 -m "..."`

## Changelog Management

It's recommended to maintain a `CHANGELOG.md` file:

```markdown
# Changelog

All notable changes to Cyber-Lighthouse are documented here.

## [1.1.0] - 2026-03-31

### Added
- Web content scraping with trafilatura
- Semantic topic clustering with embeddings
- Daily synthesis report generation
- Teams webhook integration

### Changed
- Updated database schema with topics table
- Improved error handling and logging

### Fixed
- Fixed cache clearing on reset

## [1.0.0] - 2026-03-30

### Added
- Initial release
- Real-time RSS monitoring
- Gemini AI analysis
- SQLite database
```

Update manually after each version bump.

## Best Practices

✅ **Do**:
- Use semantic versioning consistently
- Bump version before release
- Create git tags for releases
- Update changelog
- Test before bumping
- Commit all changes first

❌ **Don't**:
- Bump version without releasing
- Skip git tagging
- Use inconsistent version formats
- Bump version mid-development
- Force push after creating tags

## CI/CD Integration

For automated releases, you can integrate with CI/CD:

```yaml
# GitHub Actions example
- name: Bump Version
  run: |
    python bump_version.py minor

- name: Push Changes
  run: |
    git push origin master
    git push origin tags
```

## Related Commands

```bash
# View current version
grep version pyproject.toml

# List all tags
git tag -l

# View tag details
git show v1.0.0

# Delete a tag
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0  # Push deletion to remote

# Revert version bump
git revert <commit-hash>
```
