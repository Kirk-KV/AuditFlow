# Contributing

Changes should keep audit work traceable, reproducible, and practical.

## Setup

```bash
python -m pip install -c requirements-dev.lock -e ".[analysis,test]"
auditflow --help
```

`requirements-dev.lock` pins the direct dependencies selected for development and CI. End users do not need this file for a normal AuditFlow installation.

## Checks

Run at least:

```bash
python -m compileall auditflow
auditflow validate --project examples/procurement_audit
python -m pytest -q
```

The Quarto integration job is configured to use Quarto 1.8.27.

If you change schemas, validate the synthetic example files against the updated schemas.

## Development Principles

- Keep source files and generated files clearly separated.
- Preserve manually edited fields when regenerating artifacts.
- Do not commit real audit evidence, confidential data, secrets, or client-specific materials.
- Prefer small, explicit YAML structures over hidden state.
- Keep examples synthetic and safe to publish.

## Documentation

Update documentation when a command, folder, template, or source-of-truth file changes.

## Release

1. Change `auditflow.__version__` in `auditflow/__init__.py`.
2. Move the completed items from `Unreleased` in `CHANGELOG.md` to
   `## <version> - <YYYY-MM-DD>` and add a new empty `Unreleased` section.
3. Run the checks and build the wheel:

```powershell
python -m compileall auditflow
python -m pytest -q
python -m pip wheel . --no-deps --no-build-isolation --wheel-dir dist
auditflow --version
```

4. Commit and create an annotated tag matching the package version:

```powershell
git add .
git commit -m "Release <version>"
git tag -a "v<version>" -m "AuditFlow <version>"
git push origin main --follow-tags
```

5. In GitHub, open **Releases**, choose **Draft a new release**, select the tag, use the matching changelog section as release notes, attach the wheel from `dist/`, and publish.
