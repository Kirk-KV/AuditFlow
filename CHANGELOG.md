# Changelog

## Unreleased

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
- clarified that AuditFlow is an engagement framework, not an audit management system.

## 0.1.0

Initial public prototype:

- staged audit project structure;
- CLI artifact generation for planning, audit program, workpapers, observations, report, feedback, and archive;
- project-level report and archive styling;
- event-based timeline facts;
- basic project validation.
