# VS Code и CLI

[English](../vscode_cli.md) | **Русский**

## Создание проекта

```powershell
auditflow init "C:/Audits/2026-001" --language ru
```

Основные команды:

```powershell
auditflow status
auditflow create planning
auditflow create audit-program
auditflow create workpapers
auditflow create observations
auditflow create report
auditflow feedback request
auditflow feedback summary
auditflow create archive
auditflow timeline refresh
auditflow evidence status
auditflow evidence refresh
auditflow validate
auditflow validate --strict
```

AI-команды:

```powershell
auditflow ai status
auditflow ai draft-observation WP-C-001
auditflow ai review-observation OBS-001
auditflow ai review-audit-program
```

`WP-C-001` и `OBS-001` — идентификаторы конкретных артефактов проекта.

После заполнения `01_planning/planning_decision.yml` повторите
`auditflow create planning`, чтобы обновить таблицы рисков, контролей и тестов.
Команда `auditflow create audit-program` формирует программу в YAML и таблицу
в `03_audit_program/audit_program.qmd`. Правьте гипотезы и процедуры в YAML и
повторяйте команду без `--overwrite`.

Повторный запуск `create workpapers` обновляет заголовок и сохраняет тело
рабочего документа. `create observations` обновляет заголовок из предложения
в рабочем документе и связанные поля из программы аудита, сохраняя ручной
текст, оценку значимости и план мероприятий. Для списков и переносов строк
в полях наблюдения используйте Markdown внутри многострочного блока YAML (`|`).

## Quarto

Предварительный просмотр одного документа:

```powershell
quarto preview 01_planning/planning_document.qmd
```

Фиксированный HTML для передачи или архивирования:

```powershell
quarto render 07_reporting/report.qmd --to html
```

В AuditFlow QMD используют `metadata-files` и не требуют `_quarto.yml`. Для старого проекта:

1. удалите `_quarto.yml` из корня аудита;
2. добавьте актуальный `styles/quarto-html.yml`;
3. подключите его в каждом QMD через `metadata-files`.

