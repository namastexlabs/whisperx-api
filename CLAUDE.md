@AGENTS.md

# MurmurAI Project Context

## Release Automation

**NEVER manually edit version numbers.** This project has automated release workflows.

### How to Release

**Release Candidate (RC):**
```bash
# Option 1: PR with label
# Create PR → Add `rc` label → Merge to dev or main

# Option 2: Manual dispatch
gh workflow run release.yml -f action=rc
```

**Stable Release:**
```bash
# Option 1: PR with label (main branch only)
# Create PR to main → Add `stable` label → Merge

# Option 2: Manual dispatch (main branch only)
gh workflow run release.yml -f action=stable --ref main
```

### What the Workflow Does

1. **Gate Check** - Validates release conditions (labels, branch)
2. **Bump Version** - Runs `scripts/bump_version.py --action <rc|stable>`
   - `rc`: 1.0.1 → 1.0.2-rc.1, or 1.0.2-rc.1 → 1.0.2-rc.2
   - `stable`: 1.0.2-rc.5 → 1.0.2
3. **Commit & Tag** - Creates `chore: release vX.Y.Z` commit and git tag
4. **Build** - Uses `uv build` to create wheel/sdist
5. **Publish** - Pushes to PyPI via trusted publishing
6. **GitHub Release** - Creates release with auto-generated notes

### CI Pipeline

Every push runs:
- **Lint**: `ruff check` + `ruff format --check`
- **Type Check**: `mypy src/`
- **Test**: `pytest tests/` with coverage

### Version Files

Version is stored in two places (both updated by bump script):
- `pyproject.toml` - line 8: `version = "X.Y.Z"`
- `src/murmurai_server/__init__.py` - line 3: `__version__ = "X.Y.Z"`

### Branch Strategy

- `dev` - Development branch (RC releases)
- `main` - Production branch (stable releases only)
- Feature branches → PR to `dev`
- `dev` → PR to `main` for stable release
