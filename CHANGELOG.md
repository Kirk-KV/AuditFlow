# Changelog

## Unreleased

## 0.2.0 - 2026-08-04

- added Russian document templates selected with `auditflow init --language ru`;
- added project language settings, Russian workpaper parsing, and Russian documentation;
- added OpenAI-compatible and Anthropic Claude provider adapters with structured output;
- made automatic AI output language follow the project language;
- added `auditflow --version` and a single package-version source;
- fixed and consolidated the procurement example analysis;
- added candidate review evidence and reproducible example tests;
- added optional analysis and test dependencies;
- added automatic validation of Markdown evidence links in workpapers;
- expanded structural validation and added finalization-oriented strict mode;
- added GitHub Actions checks for Python, wheel packaging, and Quarto rendering;
- added an end-to-end CLI lifecycle regression test;
- added direct development dependency constraints and package metadata;
- prevented example evidence links in new workpapers from being validated as real files;
- preserved empty evidence folders in Git so validation works after a clean checkout;
- made synthetic generated CSV hashes stable across Windows and Linux;
- replaced Quarto project configuration with shared per-document metadata so
  rendering works reliably from Windows network and DFS drives;
- clarified that AuditFlow is an engagement framework, not an audit management system.

## 0.1.0

Initial public prototype:

- staged audit project structure;
- CLI artifact generation for planning, audit program, workpapers, observations, report, feedback, and archive;
- project-level report and archive styling;
- event-based timeline facts;
- basic project validation.
