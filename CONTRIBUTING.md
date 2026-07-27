# Contributing

AuditFlow is a file-based internal audit workflow tool. Changes should keep audit work traceable, reproducible, and practical.

## Setup

```bash
python -m pip install -c requirements-dev.lock -e ".[analysis,test]"
auditflow --help
```

`requirements-dev.lock` pins the direct dependencies selected for development
and CI. End users do not need this file for a normal AuditFlow installation.

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
