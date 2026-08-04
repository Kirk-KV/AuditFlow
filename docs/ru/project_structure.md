# Структура проекта

[English](../project_structure.md) | **Русский**

```text
audit-project/
├── initial_data.yml
├── 00_admin/
│   ├── settings.yml
│   ├── stakeholders.yml
│   ├── team.yml
│   ├── timeline.yml
│   └── ai.yml
├── 01_planning/
├── 02_notification/
├── 03_audit_program/
├── 04_evidence/
│   ├── 01_regulations/
│   ├── 02_raw_data/
│   ├── 03_correspondence/
│   ├── 04_reference_materials/
│   ├── 05_screenshots/
│   └── 99_generated/
├── 05_workpapers/
├── 06_observations/
├── 07_reporting/
├── 08_feedback/
├── 09_archive/
└── styles/
```

`00_admin/settings.yml` хранит язык человекочитаемых документов:

```yaml
language: ru
```

YAML-ключи, ID, статусы и имена каталогов одинаковы для английских и русских проектов. Это позволяет использовать одни схемы, валидаторы и команды.

Исходные доказательства помещаются в `04_evidence`; производные результаты анализа — в `04_evidence/99_generated`. Git обычно не хранит сами конфиденциальные файлы, но может хранить evidence manifest с их SHA-256.

В проекте нет `_quarto.yml`. Каждый QMD подключает `styles/quarto-html.yml` через `metadata-files`, поэтому Quarto не обязан создавать проектные временные Sass-файлы на сетевом диске (сделано намеренно, т.к. _quarto.yml не работал как задумано в корпоративной среде).

