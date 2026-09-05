# Changelog

## Unreleased


## changes as of 2026-09-05

- made workpaper names unique regardless of filesystem case sensitivity and reserved existing references before assigning names to inserted controls;
- validated all workpaper references before overwriting any workpaper;
- rejected audit program rows even when planning includes no risks, and accepted company-defined risk/control IDs in observations as well as audit programs;
- made observation stamps insensitive to Git line-ending conversion and excluded local Python caches and placeholder files from the archive evidence map;
- Python callers of `update_report_qmd` and `update_archive` now receive an update result with `path` and `missing_blocks` instead of a bare `Path`. The obsolete `write_supporting_files` and `write_css` compatibility helpers were removed.

- fixed workpaper references so two controls can no longer collapse into one workpaper file: references are normalized when the audit program is generated, stay stable when the program is regenerated, and are refused rather than silently sanitized when they cannot become a file name;
- stopped imposing a format on risk and control identifiers, which come from the company's own risk register and control framework, so non-Latin identifiers work; identifiers AuditFlow generates itself keep their fixed format;
- reported a missing prerequisite file as a plain message instead of a traceback, and gave every expected failure a shared `AuditFlowError` base;
- reported deleted `AUTO` markers when creating the report or archive, instead of silently leaving the generated section out of the document;
- recorded in the report and archive which observations they were generated from, and made validation report a document that predates the current observations;
- extended validation to the ends of the traceability chain: planning risks against `initial_data.yml`, audit program rows against included risks, and the generated report and archive;
- applied the previously unused `audit` and `risks` schemas to `initial_data.yml` as drafting warnings that strict mode treats as failures;
- removed the unused evidence register schema, superseded by `04_evidence/evidence_manifest.yml`;
- removed a duplicate argparse entry point and root-detection logic from the feedback command, and consolidated YAML reading and writing into one module;
- excluded Quarto rendering from the default test run, which now takes seconds.

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
- replaced Quarto project configuration with shared per-document metadata so rendering works reliably from Windows network and DFS drives;
- clarified that AuditFlow is an engagement framework, not an audit management system.

## 0.1.0

Initial public prototype:

- staged audit project structure;
- CLI artifact generation for planning, audit program, workpapers, observations, report, feedback, and archive;
- project-level report and archive styling;
- event-based timeline facts;
- basic project validation.
